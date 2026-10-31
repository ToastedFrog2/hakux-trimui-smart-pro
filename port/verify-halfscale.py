#!/usr/bin/env python3
"""Check fractional coordinates, actual copy commands, options and GLSL."""
from pathlib import Path
import os
import subprocess
import tempfile
import tarfile

root=Path(__file__).resolve().parent
os.chdir(root)
cc=os.environ.get('CC','cc')
flags=['-std=gnu11','-O2','-DHLE_HOST_TEST=1','-DVK_NO_PROTOTYPES','-Isource',
       '-Iplatform/include','-Isource/native/compat/glib','-Ideps/volk','-Ideps/Vulkan-Headers/include']
san=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if os.environ.get('HAKUX_TEST_SANITIZE') else []
with tempfile.TemporaryDirectory(prefix='hakux-halfscale-check-') as temporary:
    temporary=Path(temporary)
    exe=temporary/'geometry'
    subprocess.run([cc,*flags,*san,'tests/halfscale.c','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

    source=Path('source/native/core/options.c').read_text()
    start=source.index('static const char *value(')
    functions=source[start:source.index('\nvoid nc_options_apply(',start)]
    init_start=source.index('void nc_options_init(')
    init=source[init_start:source.index('\nstatic const char *value(',init_start)]
    prefix=r'''
#include "native/core/options.h"
#include "hakux/render_scale.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static float chosen=1;
static void nc_hle_set_render_scale(float n) { chosen=hle_scale_clamp(n); }
static bool nc_net_option(const char *s) { return false; }
static void nc_core_set_relaunch(bool b) {}
static void nc_core_set_loadstate(const char *s) {}
static void nc_mods_set_manifest(const char *s) {}
static void nc_state_set_core_version(const char *s) {}
static void nc_kernel_set_language(int n) {}
static void nc_kernel_set_clock(long long n) {}
static void nc_kernel_set_time_zone(int n) {}
static void nc_log(const char *s,const char *format,...) {}
enum { NC_AV_PACK_STANDARD,NC_AV_PACK_SVIDEO,NC_AV_PACK_SCART,NC_AV_PACK_VGA,NC_AV_PACK_HDTV };
'''
    main=r'''
int main(void) {
    NcOptions o;
    setenv("HAKUX_RENDER_SCALE","0.5",1); nc_options_init(&o); assert(chosen==.5f);
    assert(nc_option(&o,"scale=0.35")); assert(chosen==.35f);
    setenv("HAKUX_RENDER_SCALE","0.35",1); nc_options_init(&o); assert(chosen==.35f);
    assert(nc_option(&o,"scale=0.75")); assert(chosen==.75f);
    setenv("HAKUX_RENDER_SCALE","0.75",1); nc_options_init(&o); assert(chosen==.75f);
    assert(nc_option(&o,"scale=1")); assert(chosen==1);
    assert(nc_option(&o,"scale=0.5")); assert(chosen==.5f);
    assert(nc_option(&o,"scale=nan")); assert(chosen==1);
    assert(nc_option(&o,"scale=4")); assert(chosen==4);
    puts("PASS actual option parser: 0.5x via environment/CLI, integer scales and invalid input");
}
'''
    path=temporary/'options.c'; path.write_text(prefix+init+functions+main)
    subprocess.run([cc,*flags,*san,str(path),'-o',str(temporary/'options')],check=True)
    subprocess.run([str(temporary/'options')],check=True)

    back=Path('source/hw/xbox/hle/vk/back.c').read_text()
    start=back.index('static void cmd_copy(')
    copy=back[start:back.index('\n/* Texels the CPU wrote',start)]
    prefix=r'''
#include "hw/xbox/hle/base.h"
#include "hw/xbox/hle/vk/back_int.h"
#include "hw/xbox/hle/front/cmd.h"
static struct VolkDeviceTable test_table;
#define T test_table
static struct { struct { unsigned copy_skips,copies; } st; } g_back;
static HleVkSurf surfaces[3];
enum { PE_COPY };
static void close_pass_why(int n) {}
HleVkSurf *hle_surf_get(uint32_t n) { return n>0 && n<3 ? &surfaces[n] : NULL; }
bool hle_surf_ensure(HleVkSurf *s) { return true; }
void hle_surf_transition(VkCommandBuffer b,HleVkSurf *s,VkImageLayout l) { s->layout=l; }
void hle_surf_written(HleVkSurf *s) {}
static VkCommandBuffer cb_get(void) { return (VkCommandBuffer)(uintptr_t)1; }
void hle_log(const char *s,const char *fmt,...) {}
static unsigned copies,blits;
static VkImageCopy2 last_copy;
static VkImageBlit2 last_blit;
static void VKAPI_CALL copy_record(VkCommandBuffer b,const VkCopyImageInfo2 *i) {
 copies++; assert(i->regionCount==1); last_copy=i->pRegions[0];
}
static void VKAPI_CALL blit_record(VkCommandBuffer b,const VkBlitImageInfo2 *i) {
 blits++; assert(i->regionCount==1); last_blit=i->pRegions[0];
}
'''
    main=r'''
static void setup(float a,float b) {
 for(unsigned i=1;i<=2;i++) {
  HleVkSurf *s=&surfaces[i]; memset(s,0,sizeof(*s)); s->d.w=641; s->d.h=481;
  s->scale=i==1?a:b; s->w=hle_scale_extent(s->d.w,s->scale); s->h=hle_scale_extent(s->d.h,s->scale);
  s->img=(VkImage)(uintptr_t)i; s->aspect=VK_IMAGE_ASPECT_COLOR_BIT; s->fmt=VK_FORMAT_R8G8B8A8_UNORM;
  s->layout=VK_IMAGE_LAYOUT_GENERAL;
 }
 copies=blits=0;
}
int main(void) {
 T.vkCmdCopyImage2=copy_record; T.vkCmdBlitImage2=blit_record;
 HleCmdCopy c={0}; c.src=1; c.dst=2; c.nrects=1; c.rect[0]=(HleRect){0,0,640,480};
 setup(.35f,.35f); cmd_copy(&c); assert(copies==1 && !blits);
 assert(last_copy.extent.width==224 && last_copy.extent.height==168);
 setup(.35f,.5f); cmd_copy(&c); assert(!copies && blits==1);
 assert(last_blit.srcOffsets[1].x==224 && last_blit.dstOffsets[1].x==320);
 setup(.75f,.75f); cmd_copy(&c); assert(copies==1 && !blits);
 assert(last_copy.extent.width==480 && last_copy.extent.height==360);
 setup(.75f,.5f); cmd_copy(&c); assert(!copies && blits==1);
 assert(last_blit.srcOffsets[1].x==480 && last_blit.dstOffsets[1].x==320);
 setup(.75f,1); cmd_copy(&c); assert(!copies && blits==1);
 assert(last_blit.srcOffsets[1].x==480 && last_blit.dstOffsets[1].x==640);
 setup(.75f,.75f); c.rect[0]=(HleRect){0,0,641,481}; cmd_copy(&c);
 assert(copies==1 && last_copy.extent.width==481 && last_copy.extent.height==361);
 c.rect[0]=(HleRect){0,0,640,480};
 setup(.5f,.5f); cmd_copy(&c); assert(copies==1 && !blits);
 assert(last_copy.extent.width==320 && last_copy.extent.height==240);
 setup(.5f,1); cmd_copy(&c); assert(!copies && blits==1);
 assert(last_blit.srcOffsets[1].x==320 && last_blit.dstOffsets[1].x==640);
 setup(.5f,.5f); c.rect[0]=(HleRect){1,1,4,4}; cmd_copy(&c);
 assert(last_copy.extent.width==2 && last_copy.extent.height==2);
 setup(.5f,.5f); c.rect[0]=(HleRect){0,0,2,2}; c.x[0]=1; c.y[0]=1; cmd_copy(&c);
 assert(!copies && blits==1 && last_blit.dstOffsets[0].x==0 && last_blit.dstOffsets[1].x==2);
 setup(1,1); c.rect[0]=(HleRect){0,0,640,480}; c.x[0]=c.y[0]=0; cmd_copy(&c);
 assert(copies==1 && last_copy.extent.width==640 && last_copy.extent.height==480);
 setup(.5f,.5f); c.rect[0]=(HleRect){0,0,641,481}; cmd_copy(&c);
 assert(copies==1 && last_copy.extent.width==321 && last_copy.extent.height==241);
 puts("PASS actual image-copy commands: 0.5x/1x, mixed scales, odd origins/extents, bounded Vulkan regions");
}
'''
    path=temporary/'copy.c'; path.write_text(prefix+copy+main)
    subprocess.run([cc,*flags,*san,str(path),'-o',str(temporary/'copy')],check=True)
    subprocess.run([str(temporary/'copy')],check=True)

    # Generate representative FF, programmable and register-combiner shaders
    # from the actual sources, then validate all with native glslang.
    vtest=Path('source/tests/hle/test_vsh.c').read_text()
    tokens=vtest[vtest.index('static const uint32_t k_prog'):vtest.index('static void dump(')]
    fixture=r'''
#include "hw/xbox/hle/shader/ff.h"
#include "hw/xbox/hle/shader/psh.h"
#include "hw/xbox/hle/shader/vsh.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
'''+tokens+r'''
static char output[65536];
static void save(const char *dir,const char *name,unsigned mode,const char *ext) {
 if(mode&1) assert(hle_glsl_fixed_slots(output,sizeof(output))>0 || !strstr(output,"uTex2D[];"));
 char path[1024]; snprintf(path,sizeof(path),"%s/%s-%u.%s",dir,name,mode,ext);
 FILE *f=fopen(path,"wb"); assert(f); fputs(output,f); fclose(f);
}
int main(int argc,char **argv) {
 for(unsigned mode=0;mode<12;mode++) {
  g_hle_push_ssbo=(mode&2)!=0;
  g_hle_glsl_scale035=mode>=4 && mode<8;
  g_hle_glsl_scale075=mode>=8;
  HleFfVsKey vs={0}; vs.fvf=HLE_FVF_XYZ|HLE_FVF_DIFFUSE|(1u<<8); vs.ntex=1; vs.points=1;
  assert(hle_ff_vs_glsl(&vs,output,sizeof(output))>0); save(argv[1],"fixed-vertex",mode,"vert");
  HleFfPsKey ps={0}; ps.nstages=1; ps.st[0].texture=1; ps.st[0].colorop=4;
  ps.st[0].colorarg1=2; ps.st[0].colorarg2=0; ps.st[0].alphaop=2; ps.st[0].alphaarg1=2;
  assert(hle_ff_ps_glsl(&ps,output,sizeof(output))>0); save(argv[1],"fixed-fragment",mode,"frag");
  uint32_t rs[HLE_PS_REGS]={0}; rs[HLE_PS_COUNT]=1; rs[HLE_PS_TEXMODES]=1;
  HlePshKey pk; hle_psh_key(rs,&pk);
  assert(hle_psh_glsl(&pk,output,sizeof(output),NULL)>0); save(argv[1],"combiner",mode,"frag");
  HleVshKey vk={.in_mask=(1u<<0)|(1u<<3)|(1u<<4)};
  assert(hle_vsh_glsl(&k_prog[0][0],NSLOTS,&vk,output,sizeof(output))>0); save(argv[1],"program-vertex",mode,"vert");
 }
}
'''
    path=temporary/'shaders.c'; path.write_text(fixture)
    vsh='deps/root/subprojects/nv2a_vsh_cpu/src'
    subprocess.run([cc,*flags,'-Ideps/root','-I'+vsh,str(path),'source/hw/xbox/hle/shader/ff_gen.c',
                    'source/hw/xbox/hle/shader/psh.c','source/hw/xbox/hle/shader/vsh.c',
                    vsh+'/nv2a_vsh_disassembler.c','-o',str(temporary/'shaders')],check=True)
    subprocess.run([str(temporary/'shaders'),str(temporary)],check=True)
    compiler=root/'build/host-glslang/StandAlone/glslang'
    count=0
    for shader in sorted([*temporary.glob('*.vert'),*temporary.glob('*.frag')]):
        subprocess.run([str(compiler),'-V','--target-env','vulkan1.3',str(shader),'-o',str(temporary/'shader.spv')],
                       check=True,stdout=subprocess.DEVNULL)
        count+=1
    print(f'PASS {count} generated Vulkan shaders: FF/program vertex, FF/combiner fragment, fixed/bindless slots, push/SSBO')

    # The public baseline includes both prior fractional shader variants.
    # Check the complete generated text, since it forms the disk-cache keys.
    public_baseline=Path(os.environ.get('HAKUX_SHADER_BASELINE',str(root.parent/'sources/hakux-patched.tar.gz')))
    if public_baseline.is_file():
        old_headers=temporary/'prior-headers'
        header=old_headers/'hw/xbox/hle/shader/ff.h';header.parent.mkdir(parents=True)
        with tarfile.open(public_baseline) as saved:
            header.write_bytes(saved.extractfile('source/hw/xbox/hle/shader/ff.h').read())
        ref=temporary/'prior.c'
        ref.write_text(fixture.replace('#include <assert.h>','extern bool g_hle_glsl_scale075;\n#include <assert.h>'))
        subprocess.run([cc,'-I'+str(old_headers),*flags,'-Ideps/root','-I'+vsh,str(ref),
                        'source/hw/xbox/hle/shader/ff_gen.c','source/hw/xbox/hle/shader/psh.c',
                        'source/hw/xbox/hle/shader/vsh.c',vsh+'/nv2a_vsh_disassembler.c',
                        '-o',str(temporary/'prior')],check=True)
        prior_output=temporary/'prior-output';prior_output.mkdir()
        subprocess.run([str(temporary/'prior'),str(prior_output)],check=True)
        checked=0
        for shader in [*temporary.glob('*.vert'),*temporary.glob('*.frag')]:
            mode=int(shader.stem.rsplit('-',1)[1])
            if mode<8:
                assert shader.read_bytes()==(prior_output/shader.name).read_bytes(),shader.name
                checked+=1
            else:assert 'n == 130u ? 0.75' in shader.read_text(),shader.name
        print(f'PASS {checked} prior 0.5x/0.35x shaders byte-identical; 0.75x has a separate decoder')

    baseline=root/'versions/xbox 2 0.5 working/source-and-symbols.tar.gz'
    if baseline.is_file():
        headers=temporary/'baseline-headers'
        header=headers/'hw/xbox/hle/shader/ff.h'
        header.parent.mkdir(parents=True)
        with tarfile.open(baseline) as saved:
            header.write_bytes(saved.extractfile('source/hw/xbox/hle/shader/ff.h').read())
        # Only the shared helper differs in the saved generators. Compile the
        # current generator bodies with its exact saved header as a reference.
        reference=temporary/'reference.c'
        reference.write_text(fixture.replace('#include <assert.h>',
                             'extern bool g_hle_glsl_scale035;\nextern bool g_hle_glsl_scale075;\n#include <assert.h>'))
        subprocess.run([cc,'-I'+str(headers),*flags,'-Ideps/root','-I'+vsh,str(reference),
                        'source/hw/xbox/hle/shader/ff_gen.c','source/hw/xbox/hle/shader/psh.c',
                        'source/hw/xbox/hle/shader/vsh.c',vsh+'/nv2a_vsh_disassembler.c',
                        '-o',str(temporary/'reference')],check=True)
        reference_output=temporary/'reference-output';reference_output.mkdir()
        subprocess.run([str(temporary/'reference'),str(reference_output)],check=True)
        checked=0
        for shader in sorted([*temporary.glob('*.vert'),*temporary.glob('*.frag')]):
            mode=int(shader.stem.rsplit('-',1)[1])
            if mode<4:
                assert shader.read_bytes()==(reference_output/shader.name).read_bytes(),shader.name
                assert 'n == 129u' not in shader.read_text(),shader.name
                checked+=1
            else:
                assert 'n == 129u ? 0.35' in shader.read_text(),shader.name
        print(f'PASS {checked} complete 0.5x shaders byte-identical to saved working version; 0.35x decoder retained separately')
