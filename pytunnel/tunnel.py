from __future__ import print_function

from threading import Lock
import sys

READ_BUF_LEN = 1024
IS_PY3 = sys.version_info >= (3, 0)


def send_str(sock, msg, code=0):
    if sock:
        sock.sendall(msg.encode('utf-8'))


def start_thread(target=None, args=[]):
    import threading
    th = threading.Thread(target=target, args=args)
    th.setDaemon(True)
    th.start()
    return th


def make_package(target, data):
    package = str(target).encode() + 'L'.encode() + str(len(data)).encode() + 'D'.encode() + data
    return package


def parse_package(package=''):
    lix = package.index('L'.encode())
    target = int(package[0:lix])
    dix = package.index('D'.encode())
    len = int(package[lix + 1:dix])
    data = package[dix + 1:]
    return target, len, data


def sock_read(sock, buflen=READ_BUF_LEN):
    try:
        recv = sock.recv(buflen)
    except:
        import traceback
        # traceback.print_exc()
        recv = b''
    return recv


def sock_send(sock, data):
    if type(data) == type('') and IS_PY3:
        # str
        data = data.encode()
    try:
        sock.sendall(data)
        return True
    except:
        import traceback
        traceback.print_exc()
        return False


_sock_recv = {}


def read_package(sock):
    sockid = int(id(sock))
    head_len = 40
    if sockid in _sock_recv:
        recv = _sock_recv[sockid]
        del _sock_recv[sockid]
    else:
        recv = sock_read(sock, head_len)
    while b'L' not in recv or b'D' not in recv:
        r = sock_read(sock, head_len)
        if len(r) == 0:
            return None
        recv += r
    pk = parse_package(recv)
    if pk:
        target = pk[0]
        dlen = pk[1]
        data = pk[2]
        while len(data) < dlen:
            r = sock_read(sock, min(dlen - len(data), READ_BUF_LEN))
            if len(r) == 0:
                return None
            data += r
        if len(data) > dlen:
            _sock_recv[sockid] = data[dlen:]
            data = data[0:dlen]
    return target, data


def send_package(sock, ix, data):
    return sock_send(sock, make_package(ix, data))


def sock_close(sock, shut=False):
    if shut:
        try:
            # sock_send(sock, 'c')
            sock.shutdown(0)
        except:
            import traceback
            # traceback.print_exc()
    sock.close()


class Base(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Runable(Base):
    _thread = None
    _running = False

    def __str__(self):
        return self.__class__.__name__

    def _log(self, msg, *args):
        print(self, msg, *args)

    def _run(self):
        pass

    def _start_run(self):
        self._log('start run')
        self._run()
        self._running = False
        self._log('end run')

    def start(self):
        if not self._running:
            self._running = True
            th = start_thread(target=self._start_run)
            self._thread = th
            return th

    def stop(self):
        self._running = False
        self._log('_running', self._running)


class SockRunable(Runable):
    _sock = None

    def _run(self):
        pass

    def stop(self):
        if self._sock:
            import socket
            self._log('close _sock', self._sock)
            sock_close(self._sock)
            self._sock = None
        super(SockRunable, self).stop()


class Tunnel(SockRunable):
    sock = None
    bind = '0.0.0.0'
    port = 0
    _client_map = {}
    _client_ix = 0
    _lock = Lock()

    def __str__(self):
        return '%s[%d]' % (self.__class__.__name__, self.port)

    def _run_con(self, sock, ix):
        send_package(self.sock, ix, b'')
        while self._running:
            recv = sock_read(sock)
            # self._log('conn read', ix, len(recv), recv[0:20])
            if not self.sock:
                break
            if recv:
                if not send_package(self.sock, ix, recv):
                    self.stop()
                    break
            else:
                send_package(self.sock, -1 * ix, b'')
                sock_close(sock)
                self._del_con(ix)
                break

    def _del_con(self, ix):
        self._lock.acquire()
        if ix in self._client_map:
            self._log('disconn', ix)
            sock_close(self._client_map[ix]['sock'], True)
            del self._client_map[ix]
        self._lock.release()

    def _add_con(self, sock, addr):
        self._lock.acquire()
        self._log('add %s %s' % (sock, addr))
        self._client_ix += 1

        th = start_thread(self._run_con, [sock, self._client_ix])
        self._client_map[self._client_ix] = {
            'th': th,
            'sock': sock
        }
        self._lock.release()
        return th

    def _run_sock(self):
        while self._running:
            recv = read_package(self.sock)
            if recv:
                ix, data = recv
                if ix > 0:
                    if ix in self._client_map:
                        d = self._client_map[ix]
                        # self._log('trans', ix, data[0:20])
                        sock_send(d['sock'], data)
                else:
                    self._del_con(abs(ix))
            else:
                self.stop()

    def _run(self):
        import socket
        try:
            th = start_thread(target=self._run_sock)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('binding @%s:%s' % (self.bind, self.port))
            sock.bind((self.bind, self.port), )
            sock.listen(1000)
            self._sock = sock
            self._log('running tunnel @%s:%s' % (self.bind, self.port))
            while self._running:
                try:
                    clt_con, clt_add = sock.accept()
                    ret = self._add_con(clt_con, clt_add)
                    if not ret:
                        sock_close(clt_con)
                except:
                    import traceback
                    traceback.print_exc()
                    self.stop()
        except Exception as e:
            import traceback
            traceback.print_exc()
            # send_str(self.sock, str(e))
            send_package(self.sock, 0, str(e).encode())

    def stop(self):
        self._lock.acquire()
        if self.sock:
            self._log('close sock', self.sock)
            sock_close(self.sock)
            self.sock = None
        for d in self._client_map.values():
            sock_close(d['sock'])
        self._client_map.clear()
        super(Tunnel, self).stop()
        self._log('stop')
        self._lock.release()


class Server(SockRunable):
    bind = '0.0.0.0'
    port = 1990
    passwd = '123'

    def _ready(self, sock, addr):
        import json
        auth = sock_read(sock)
        self._log('auth', auth)
        data = json.loads(auth, encoding='utf-8')
        self._log('tun req data', data)
        if self.passwd and self.passwd != data.get('passwd'):
            # send_str(sock, 'password error!')
            send_package(sock, 0, 'password error!'.encode())
            return
        kwargs = {'sock': sock}
        for k in ['bind', 'port']:
            if data.get(k):
                kwargs[k] = data[k]
        tun = Tunnel(**kwargs)
        tun.start()
        return tun

    def _run(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._log('binding @%s:%s' % (self.bind, self.port))
        sock.bind((self.bind, self.port), )
        sock.listen(1000)
        self._sock = sock
        self._log('running server @%s:%s' % (self.bind, self.port))
        while self._running:
            try:
                clt_con, clt_add = self._sock.accept()
                self._log('new tun req', clt_con, clt_add)
                try:
                    ret = self._ready(clt_con, clt_add)
                    if not ret:
                        sock_close(clt_con)
                except:
                    import traceback
                    traceback.print_exc()
            except:
                import traceback
                traceback.print_exc()
                self.stop()


class Client(SockRunable):
    server = '192.168.1.102'
    port = 1990
    passwd = '123'
    proxy_port = 1091

    target_host = '127.0.0.1'
    target_port = 6379

    _client_map = {}

    def _run_con(self, ix, sock):
        while self._running:
            recv = sock_read(sock)
            # self._log('conn read', ix, len(recv), recv[0:20])
            if len(recv):
                send_package(self._sock, ix, recv)
            else:
                send_package(self._sock, -1 * ix, b'')
                sock_close(sock)
                self._log('do discon', ix)
                break

    def _add_con(self, ix):
        import socket
        try:
            self._log('add conn', ix)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('connecting target @%s:%s' % (self.target_host, self.target_port))
            sock.connect((self.target_host, self.target_port), )
            self._log('connected target @%s:%s' % (self.target_host, self.target_port))
            self._client_map[ix] = {
                'sock': sock,
                'th': start_thread(target=self._run_con, args=[ix, sock])
            }
            return self._client_map[ix]
        except:
            import traceback
            traceback.print_exc()

    def _run(self):
        import socket, json
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock = sock
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('connecting server @%s:%s' % (self.server, self.port))
            sock.connect((self.server, self.port), )
            sock_send(sock, json.dumps({'passwd': self.passwd, 'port': self.proxy_port}))
        except:
            import traceback
            traceback.print_exc()
            return
        self._log('connected server @%s:%s' % (self.server, self.port))

        # th = start_thread(target=self._run_sock)
        self._log('tunnel', '%s:%s' % (self.target_host, self.target_port), '<->', '%s:%s' % (self.server, self.proxy_port))
        while self._running:
            recv = read_package(sock)
            if recv:
                ix, data = recv
                if ix > 0:
                    if ix not in self._client_map:
                        # new connect
                        d = self._add_con(ix)
                    else:
                        d = self._client_map[ix]
                    if d:
                        if len(data):
                            # self._log('trans', ix, data[0:20])
                            sock_send(d['sock'], data)
                    else:
                        send_package(sock, -1 * ix, b'')
                elif ix == 0:
                    self._log('\033[31m%s\033[0m' % data.decode())
                    self.stop()
                else:
                    nix = abs(ix)
                    if nix in self._client_map:
                        d = self._client_map[nix]
                        sock_close(d['sock'])
                        del self._client_map[nix]
                        self._log('discon', nix)
            else:
                self.stop()

    def stop(self):
        for d in self._client_map.values():
            sock_close(d['sock'])
        self._client_map.clear()
        super(Client, self).stop()
        self._log('stop')


def parse_endpoint(s):
    import re
    rs = re.findall('^(\S+):(\d+)$', s)
    if not rs:
        raise Exception(u'%s not a endpoint type!' % s)
    r = rs[0]
    return r[0], int(r[1])


def main():
    import time, signal, argparse
    parser = argparse.ArgumentParser(add_help=True)

    parser.add_argument('--target', help='target endpoint, such as: 127.0.0.1:8080', type=parse_endpoint)
    parser.add_argument('--server', help='server endpoint, such as: 192.168.1.3:1990', type=parse_endpoint)
    parser.add_argument('--port', help='server proxy port, such as: 1090', type=int)

    parser.add_argument('--bind', help='the server bind endpoint, such as: 0.0.0.0:1990', type=parse_endpoint)

    parser.add_argument('--passwd', help='the password, default is empty', type=str, default='')
    args = parser.parse_args()
    if args.bind:
        # server
        d = {
            'bind': args.bind[0],
            'port': args.bind[1],
            'passwd': args.passwd,
        }
        run = Server(**d)
    elif args.server and args.target:
        # client
        d = {
            'server': args.server[0],
            'port': args.server[1],
            'proxy_port': args.port,
            'target_host': args.target[0],
            'target_port': args.target[1],
            'passwd': args.passwd,
        }
        run = Client(**d)
    else:
        parser.print_help()
        exit(-1)

    def stop(a, b):
        print('stop')
        run.stop()

    signal.signal(signal.SIGINT, stop)

    run.start()
    while run._running:
        time.sleep(1)
    time.sleep(1)


if __name__ == '__main__':
    main()
