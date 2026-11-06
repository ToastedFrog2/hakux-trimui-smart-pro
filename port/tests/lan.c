#ifdef NDEBUG
#undef NDEBUG
#endif
/* Exercise the unmodified LAN backend with a real local UDP peer. */
#include "native/net/lan.c"
#include <assert.h>
#include <stdarg.h>

static NcNetConfig config;
static const uint8_t guest_mac[6]={2,0,0,0,0,1};
static unsigned delivered;
static uint8_t received[NC_NET_FRAME_MAX];
static size_t received_len;
const NcNetConfig *nc_net_config(void) {return &config;}
bool nc_net_mac(uint8_t mac[6]) {memcpy(mac,guest_mac,6);return true;}
void nc_net_twin(uint32_t ip) {assert(!"unexpected twin");}
void nc_net_deliver(const uint8_t *p,size_t len) {
    assert(len<=sizeof(received));memcpy(received,p,len);received_len=len;delivered++;
}
void nc_log(const char *tag,const char *fmt,...) {
    va_list ap;va_start(ap,fmt);vfprintf(stderr,fmt,ap);fputc('\n',stderr);va_end(ap);
}
static int bound_socket(uint16_t *port) {
    int fd=socket(AF_INET,SOCK_DGRAM,0);assert(fd>=0);
    struct sockaddr_in at={.sin_family=AF_INET,.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    assert(bind(fd,(struct sockaddr *)&at,sizeof(at))==0);
    socklen_t n=sizeof(at);assert(getsockname(fd,(struct sockaddr *)&at,&n)==0);
    *port=ntohs(at.sin_port);return fd;
}
static void pump(void) {
    struct pollfd fds[1];int timeout=200;
    assert(nc_net_lan.fill(fds,1,&timeout)==1);
    assert(poll(fds,1,200)>=0);nc_net_lan.poll(fds,1);
}
static ssize_t peer_read(int fd,uint8_t *buf,size_t cap) {
    struct pollfd p={.fd=fd,.events=POLLIN};
    assert(poll(&p,1,1000)==1);return recv(fd,buf,cap,0);
}
int main(void) {
    uint16_t peer_port,lan_port;
    int peer=bound_socket(&peer_port),reserve=bound_socket(&lan_port);close(reserve);
    config=(NcNetConfig){.lan_port=lan_port,.lan_bcast=htonl(INADDR_LOOPBACK),.npeers=1,
        .peer_ip={htonl(INADDR_LOOPBACK)},.peer_port={peer_port}};
    assert(nc_net_lan.init());
    uint8_t frame[60]={255,255,255,255,255,255},buf[NC_NET_FRAME_MAX];
    memcpy(frame+6,guest_mac,6);frame[12]=8;frame[14]=42;
    nc_net_lan.input(frame,sizeof(frame));
    assert(peer_read(peer,buf,sizeof(buf))==sizeof(frame)&&!memcmp(buf,frame,sizeof(frame)));
    /* Learn a peer from its incoming frame, then address it directly. */
    memcpy(frame,guest_mac,6);frame[11]=2;frame[14]=43;
    struct sockaddr_in to={.sin_family=AF_INET,.sin_port=htons(lan_port),
        .sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    assert(sendto(peer,frame,sizeof(frame),0,(struct sockaddr *)&to,sizeof(to))==sizeof(frame));
    pump();assert(delivered==1&&received_len==sizeof(frame)&&!memcmp(received,frame,sizeof(frame)));
    /* Drain the backend's internal discovery hello; it is not guest data. */
    assert(peer_read(peer,buf,sizeof(buf))==60&&is_hello(buf,60));
    config.npeers=0;frame[5]=2;memcpy(frame+6,guest_mac,6);frame[14]=44;
    nc_net_lan.input(frame,sizeof(frame));
    assert(peer_read(peer,buf,sizeof(buf))==sizeof(frame)&&!memcmp(buf,frame,sizeof(frame)));
    /* Ignore malformed datagrams and echoed frames carrying our own MAC. */
    assert(sendto(peer,frame,sizeof(frame),0,(struct sockaddr *)&to,sizeof(to))==sizeof(frame));
    uint8_t oversize[NC_NET_FRAME_MAX+1]={0};
    assert(sendto(peer,oversize,sizeof(oversize),0,(struct sockaddr *)&to,sizeof(to))==sizeof(oversize));
    assert(sendto(peer,oversize,1,0,(struct sockaddr *)&to,sizeof(to))==1);
    pump();assert(delivered==1);
    close(g_lan.fd);close(peer);
    puts("PASS actual LAN backend: UDP frame exchange, peer learning/unicast, echo and malformed-frame rejection");
}
