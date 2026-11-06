#include "hakux/capture.h"
int main(int argc,char **argv){return argc!=2 || !hakux_png_opaque(argv[1]);}
