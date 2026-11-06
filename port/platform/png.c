/* Framebuffer PNG normalization; runs only after a requested screenshot. */
#include "hakux/capture.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <zlib.h>

static uint32_t be32(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static void put32(uint8_t *p,uint32_t n)
{ p[0]=n>>24;p[1]=n>>16;p[2]=n>>8;p[3]=n; }
static bool chunk(FILE *f,const char *type,const uint8_t *data,uint32_t size)
{
    uint8_t n[4],c[4];put32(n,size);
    uLong crc=crc32(0,(const Bytef*)type,4);
    if(size)crc=crc32(crc,data,size);
    put32(c,(uint32_t)crc);
    return fwrite(n,1,4,f)==4 && fwrite(type,1,4,f)==4 &&
           (!size || fwrite(data,1,size,f)==size) && fwrite(c,1,4,f)==4;
}
static uint8_t paeth(uint8_t a,uint8_t b,uint8_t c)
{
    int p=(int)a+b-c,da=abs(p-a),db=abs(p-b),dc=abs(p-c);
    return da<=db && da<=dc?a:db<=dc?b:c;
}
bool hakux_png_opaque(const char *path)
{
    static const uint8_t signature[]={137,80,78,71,13,10,26,10};
    uint8_t *input=NULL,*packed=NULL,*raw=NULL,*rgb=NULL,*zip=NULL;
    char temp[1024];temp[0]=0;bool owned=false,ok=false;
    FILE *f=fopen(path,"rb");if(!f)return false;
    if(fseek(f,0,SEEK_END))goto done;
    long end=ftell(f);if(end<45 || end>24*1024*1024 || fseek(f,0,SEEK_SET))goto done;
    size_t size=(size_t)end;
    input=malloc(size);if(!input || fread(input,1,size,f)!=size || memcmp(input,signature,8))goto done;
    fclose(f);f=NULL;
    size_t at=8,npacked=0;uint32_t w=0,h=0;unsigned bpp=0;bool ended=false;
    while(at+12<=size) {
        uint32_t n=be32(input+at);if(n>size-at-12)goto done;
        const uint8_t *type=input+at+4,*data=input+at+8;
        if((uint32_t)crc32(0,type,(uInt)n+4)!=be32(data+n))goto done;
        if(!memcmp(type,"IHDR",4)) {
            if(at!=8 || n!=13 || data[8]!=8 || (data[9]!=2 && data[9]!=6) || data[10] || data[11] || data[12])goto done;
            w=be32(data);h=be32(data+4);bpp=data[9]==6?4:3;
            if(!w || !h || w>4096 || h>4096 || (uint64_t)w*h>4096*2160)goto done;
        } else if(!memcmp(type,"IDAT",4)) {
            if(!bpp || npacked+n>24*1024*1024)goto done;
            uint8_t *p=realloc(packed,npacked+n+1);if(!p)goto done;packed=p;
            memcpy(packed+npacked,data,n);npacked+=n;
        } else if(!memcmp(type,"IEND",4)) {
            if(n || at+12!=size)goto done;ended=true;break;
        } else if(!(type[0]&32))goto done; /* Unsupported critical chunk. */
        at+=n+12;
    }
    if(!ended || !npacked || !bpp)goto done;
    size_t stride=(size_t)w*bpp,rawlen=(stride+1)*h,rgbrow=(size_t)w*3+1,rgblen=rgbrow*h;
    raw=malloc(rawlen);rgb=malloc(rgblen);if(!raw || !rgb)goto done;
    uLongf unpacked=rawlen;
    if(uncompress(raw,&unpacked,packed,npacked)!=Z_OK || unpacked!=rawlen)goto done;
    for(uint32_t y=0;y<h;y++) {
        uint8_t *row=raw+(stride+1)*y+1,*prior=y?row-(stride+1):NULL,*out=rgb+rgbrow*y;
        unsigned filter=row[-1];if(filter>4)goto done;
        for(size_t x=0;x<stride;x++) {
            uint8_t a=x>=bpp?row[x-bpp]:0,b=prior?prior[x]:0,c=prior&&x>=bpp?prior[x-bpp]:0;
            if(filter==1)row[x]+=a;
            else if(filter==2)row[x]+=b;
            else if(filter==3)row[x]+=(unsigned)(a+b)/2;
            else if(filter==4)row[x]+=paeth(a,b,c);
        }
        out[0]=0;
        for(uint32_t x=0;x<w;x++)memcpy(out+1+x*3,row+x*bpp,3);
    }
    uLongf zipped=compressBound(rgblen);zip=malloc(zipped);
    if(!zip || compress2(zip,&zipped,rgb,rgblen,6)!=Z_OK)goto done;
    if(snprintf(temp,sizeof(temp),"%s.opaque-XXXXXX",path)>=(int)sizeof(temp))goto done;
    int fd=mkstemp(temp);if(fd<0)goto done;owned=true;
    f=fdopen(fd,"wb");if(!f){close(fd);goto done;}
    uint8_t ihdr[13]={0};put32(ihdr,w);put32(ihdr+4,h);ihdr[8]=8;ihdr[9]=2;
    ok=fwrite(signature,1,8,f)==8 && chunk(f,"IHDR",ihdr,13) &&
       chunk(f,"IDAT",zip,zipped) && chunk(f,"IEND",NULL,0);
    if(fflush(f) || fsync(fileno(f)))ok=false;
    if(fclose(f))ok=false;f=NULL;
    if(ok)ok=rename(temp,path)==0;
done:
    if(f)fclose(f);
    if(owned)unlink(temp);
    free(input);free(packed);free(raw);free(rgb);free(zip);
    return ok;
}
