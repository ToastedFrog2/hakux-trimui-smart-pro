#include "hakux/render_scale.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    assert(hle_scale_clamp(.75f)==.75f);
    assert(hle_scale_code(.75f)==130 && hle_scale_decode(130)==.75f);
    assert(hle_scale_extent(640,.75f)==480 && hle_scale_extent(480,.75f)==360);
    assert(hle_scale_extent(641,.75f)==481 && hle_scale_extent(481,.75f)==361);
    assert(hle_scale_extent(1,.75f)==1 && hle_scale_extent(0,.75f)==0);
    assert(hle_scale_samples(9,1,.75f)==16 && hle_scale_samples(9,0,.75f)==16);
    assert(hle_scale_samples(UINT64_MAX,UINT32_MAX,.75f)==UINT32_MAX);
    for(unsigned n=0;n<100000;n++)for(unsigned d=1;d<12;d++)
        assert(hle_scale_samples(n,d,.75f)==(uint64_t)n*16/(9*d));
    assert(hle_scale_clamp(.35f)==.35f);
    assert(hle_scale_decode(hle_scale_code(.35f))==.35f);
    assert(hle_scale_extent(640,.35f)==224 && hle_scale_extent(480,.35f)==168);
    assert(hle_scale_extent(641,.35f)==225 && hle_scale_extent(1,.35f)==1);
    assert(hle_scale_samples(49,1,.35f)==400);
    assert(hle_scale_samples(UINT64_MAX,UINT32_MAX,.35f)==UINT32_MAX);
    for(unsigned n=0;n<100000;n++)for(unsigned d=1;d<12;d++)
        assert(hle_scale_samples(n,d,.35f)==(uint64_t)n*400/(49*d));
    assert(hle_scale_extent(640,.5f)==320 && hle_scale_extent(480,.5f)==240);
    assert(hle_scale_extent(641,.5f)==321 && hle_scale_extent(1,.5f)==1);
    assert(hle_scale_extent(0,.5f)==0);
    assert(hle_scale_clamp(.5f)==.5f && hle_scale_clamp(0)==1 && hle_scale_clamp(NAN)==1);
    for (unsigned scale=1;scale<=4;scale++) {
        assert(hle_scale_decode(hle_scale_code(scale))==scale);
        for (unsigned size=0;size<16384;size++) assert(hle_scale_extent(size,scale)==size*scale);
        for (unsigned n=0;n<10000;n++) {
            unsigned div=n%11+1;
            assert(hle_scale_samples(n,div,scale)==n/(div*scale*scale));
        }
    }
    assert(hle_scale_decode(hle_scale_code(.5f))==.5f);
    assert(hle_scale_decode(0)==1);
    assert(hle_scale_samples(10,1,.5f)==40 && hle_scale_samples(10,2,.5f)==20);
    assert(hle_scale_samples(UINT64_MAX,1,.5f)==UINT32_MAX);
    HleScaledRect r=hle_scale_rect(1,1,640,480,.5f,320,240);
    assert(r.x==0 && r.y==0 && r.w==320 && r.h==240);
    r=hle_scale_rect(3,3,3,5,.5f,320,240); assert(r.w==0 && r.h==0);
    const float fractions[]={.35f,.5f,.75f};
    for(unsigned i=0;i<3;i++)for (int x=-3;x<645;x++) for (int y=-3;y<485;y++) {
        unsigned w=hle_scale_extent(640,fractions[i]),h=hle_scale_extent(480,fractions[i]);
        r=hle_scale_rect(x,y,x+7,y+9,fractions[i],w,h);
        assert(r.x>=0 && r.y>=0 && r.w<=w && r.h<=h);
        if (r.w && r.h) assert(r.x+(int)r.w<=w && r.y+(int)r.h<=h);
    }
    puts("PASS half-scale: extents, odd sizes, clipping, empty regions, sample counts and push-code round trips; 1-4x integer behavior preserved");
}
