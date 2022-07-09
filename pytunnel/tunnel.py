from __future__ import print_function

import sys, time, json
import socket

__version__ = '2.3.2'

READ_BUF_LEN = 1300
TIME_WAIT_SEND_S = 3
TIME_FOR_PING_S = 60
TIME_FOR_DOG_TIMEOUT = 60 * 2
IS_PY3 = sys.version_info >= (3, 0)


def print_it(*args):
    import datetime
    print(datetime.datetime.now(), *args)


def send_str(sock, msg, code=0):
    if sock:
        sock.sendall(msg.encode('utf-8'))


def _exit_system(code=0):
    try:
        import os
        # print('exit...')
        time.sleep(1)
        # print('exit!!!')
        os._exit(code)
    except:
        # print('exeee')
        pass


def exit_system(code=0):
    start_thread(_exit_system, args=[code])


def int_time():
    return int(time.time())


def start_thread(target=None, args=[]):
    import threading
    th = threading.Thread(target=target, args=args)
    th.setDaemon(True)
    th.start()
    return True


def make_package(target, data):
    if isinstance(data, str) and IS_PY3:
        data = data.encode()
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
    recv = b''
    if sock:
        try:
            recv = sock.recv(buflen)
        except:
            import traceback
            traceback.print_exc()
    return recv


def sock_send(sock, data):
    if type(data) == type('') and IS_PY3:
        # str
        data = data.encode()
    if sock:
        try:
            sock.sendall(data)
            return True
        except:
            import traceback
            traceback.print_exc()
    return False


def msg_to_sock(sock, msg):
    msg = '[V%s]%s' % (__version__, msg)
    send_package(sock, 0, msg.encode())


_sock_recv = {}

_sock_io_map = {}


def sock_str(sock):
    import re
    s = str(sock)
    rs = re.findall("laddr=\('(\S+)', (\d+)\), raddr=\('(\S+)', (\d+)\)", s)
    return '%s<->%s' % (rs[0][1], rs[0][3]) if rs else s


def read_package(sock):
    if not sock:
        print_it("read_package with none")
        import traceback
        traceback.print_stack()
        return
    sockid = int(id(sock))
    if sockid not in _sock_io_map:
        _sock_io_map[sockid] = SockIO(sock)
    try:
        package = _sock_io_map[sockid].recv()
        data = parse_package(package)
        if data:
            return data[0], data[2]
    except:
        import traceback
        traceback.print_exc()
    return None


def send_package(sock, ix, data):
    if not sock:
        print_it("send_package with none")
        import traceback
        traceback.print_stack()
        return
    sockid = int(id(sock))
    if sockid not in _sock_io_map:
        _sock_io_map[sockid] = SockIO(sock)
    return _sock_io_map[sockid].send(make_package(ix, data))


def sock_close(sock, shut=False):
    if not sock:
        return
    if shut:
        try:
            # sock_send(sock, 'c')
            sock.shutdown(2)
        except:
            import traceback
            # traceback.print_exc()
    # sock.send(b'')
    sock.close()
    sockid = int(id(sock))
    if sockid in _sock_io_map:
        del _sock_io_map[sockid]
        # print_it('-----sock_close-----', sock, shut)
        # import traceback
        # traceback.print_stack()
        # print_it('---end sock_close---')


class Lock(object):
    def __init__(self, name='default'):
        from threading import Lock
        self.name = name
        self.lock = Lock()

    def __enter__(self):
        # print_it('locking', self.name)
        self.lock.acquire()
        # print_it('locked', self.name)

    def __exit__(self, *unused):
        self.lock.release()
        # print_it('released', self.name)


class PackageIt(object):
    head = b'DH'
    leng = b':'
    buffer = b''

    def feed(self, data):
        if isinstance(data, str) and IS_PY3:
            data = data.encode()
        self.buffer += data

    def recv(self):
        hix = self.buffer.find(self.head)
        if hix >= 0:
            lix = self.buffer.find(self.leng, hix + len(self.head))
            if lix > 0:
                lns = self.buffer[hix + len(self.head): lix]
                pend = lix + len(self.leng) + int(lns)
                if len(self.buffer) >= pend:
                    data = self.buffer[lix + len(self.leng):pend]
                    self.buffer = self.buffer[pend:]
                    return data
        return None

    def make(self, data):
        if isinstance(data, str) and IS_PY3:
            data = data.encode()
        pack = self.head + str(len(data)).encode() + self.leng + data
        return pack


class SockIO(object):
    BUF_LEN = 1024
    _pi = PackageIt()
    _recv_lock = Lock()
    _send_lock = Lock()

    def __init__(self, sock):
        self.sock = sock
        assert sock

    def recv(self):
        with self._recv_lock:
            while True:
                data = self._pi.recv()
                if data == None:
                    r = self.sock.recv(self.BUF_LEN)
                    if not r:
                        raise Exception(u'Socket Error:%s' % str(self.sock))
                    # print(sock_str(self.sock), 'recv', r)
                    self._pi.feed(r)
                else:
                    break
            return data

    def send(self, data):
        if isinstance(data, str) and IS_PY3:
            data = data.encode()
        pack = self._pi.make(data)
        ret = False
        with self._send_lock:
            try:
                self.sock.sendall(pack)
                ret = True
            except:
                import traceback
                traceback.print_exc()
        return ret

    def close(self):
        self.sock.close()


class Base(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Runable(Base):
    _thread = None
    _running = False

    def __str__(self):
        import os
        return '%s[Pid%s]' % (self.__class__.__name__, os.getpid())

    def _log(self, msg, *args):
        print_it(self, msg, *args)

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

    _dog_runing = False
    _dog_last = 0

    def _dog_run(self):
        self._dog_last = int_time()
        while self._dog_runing:
            now = int_time()
            if (now - self._dog_last) > TIME_FOR_DOG_TIMEOUT:
                print(self, 'dog time out', now, self._dog_last)
                if not self._on_dog_timeout():
                    exit_system(-1)
            time.sleep(1)
            print('ck', self._dog_last)

    def stop_dog(self):
        self._dog_runing = False

    def start_dog(self):
        self._dog_runing = True
        start_thread(self._dog_run)

    def feed_dog(self):
        ''''''
        self._dog_last = int_time()
        # self._log('feed dog', self._dog_last)

    def _on_dog_timeout(self):
        pass


class SockRunable(Runable):
    _sock = None

    def _run(self):
        pass

    def stop(self):
        if self._sock:
            self._log('close _sock', self._sock)
            sock_close(self._sock, True)
            self._sock = None
        super(SockRunable, self).stop()

    def _on_dog_timeout(self):
        super(SockRunable, self)._on_dog_timeout()
        if self._sock:
            self.stop()


class Tunnel(SockRunable):
    sock = None
    bind = '0.0.0.0'
    port = 0
    _client_map = {}
    _client_ix = 0
    _lock = Lock()

    def __str__(self):
        return '%s[%d]' % (super(Tunnel, self).__str__(), self.port)

    def _run_con(self, sock, ix):
        send_package(self.sock, ix, b'')
        while self._running:
            recv = sock_read(sock)
            # self._log('conn read', ix, len(recv), recv[0:20])
            if not self.sock:
                break
            error = False
            if recv:
                if not send_package(self.sock, ix, recv):
                    self.stop()
                    break
            else:
                self._log('a con dis, close', ix)
                send_package(self.sock, -1 * ix, b'close')
                sock_close(sock)
                self._del_con(ix)
                break

    def _del_con(self, ix):
        with self._lock:
            if ix in self._client_map:
                self._log('disconn', ix)
                sock_close(self._client_map[ix]['sock'], True)
                del self._client_map[ix]

    def _add_con(self, sock, addr):
        with self._lock:
            self._log('add %s %s' % (sock, addr))
            self._client_ix += 1

            th = start_thread(self._run_con, [sock, self._client_ix])
            self._client_map[self._client_ix] = {
                'th': th,
                'sock': sock
            }
            return th

    def _run_sock(self):
        while self._running:
            recv = read_package(self.sock)
            if recv:
                ix, data = recv
                if ix > 0:
                    if ix in self._client_map:
                        d = self._client_map[ix]
                        # self._log('trans', ix, data)
                        sock_send(d['sock'], data)
                elif ix == 0:
                    if data == b'ping':
                        send_package(self.sock, 0, b'pong')
                    elif data == b'pong':
                        self.feed_dog()
                else:
                    self._del_con(abs(ix))
            else:
                self.stop()

    def _run_ping(self):
        while self._running:
            send_package(self.sock, 0, b'ping')
            time.sleep(TIME_FOR_PING_S)

    def _run(self):
        try:
            self._sock_th = start_thread(self._run_sock)
            self._ping_th = start_thread(self._run_ping)
            self.start_dog()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('binding %s:%s' % (self.bind, self.port))
            # sock.setblocking(False)
            sock.bind((self.bind, self.port), )
            sock.listen(1000)
            self._sock = sock
            self._log('running tunnel %s:%s' % (self.bind, self.port))
            while self._running:
                try:
                    clt_con, clt_add = sock.accept()
                    ret = False
                    if self._running:
                        ret = self._add_con(clt_con, clt_add)
                    if not ret:
                        sock_close(clt_con)
                except:
                    import traceback
                    traceback.print_exc()
                    self.stop()
            self.stop_dog()
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg_to_sock(self.sock, e)

    def stop(self):
        with self._lock:
            if self.sock:
                self._log('close sock', self.sock)
                sock_close(self.sock)
                self.sock = None
            for d in self._client_map.values():
                sock_close(d['sock'], True)
            self._client_map.clear()
            if self._sock:
                sock_close(self._sock)
                self._sock = None

                self._running = False
                # In Python2, connect to listen port to raise close and release.
                # try:
                #     s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                #     s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                #     s.connect(('127.0.0.1', self.port), )
                # except:
                #     import traceback
                #     traceback.print_exc()
            super(Tunnel, self).stop()
            self._log('stop')


class Server(SockRunable):
    bind = '0.0.0.0'
    port = 1990
    passwd = '123'
    _tunprocs_map = {}
    _tunprocs_lock = Lock()

    def _ready(self, sock, addr):
        _, auth = read_package(sock)
        # self._log('auth', auth)
        data = json.loads(auth)
        # self._log('tun req data', data)
        if self.passwd and self.passwd != data.get('passwd'):
            # send_str(sock, 'password error!')
            self._log('Password Error!!!')
            send_package(sock, 0, json.dumps({'status': 'error', 'message': "Password Error!!!"}))
            return
        send_package(sock, 0, json.dumps({'status': 'ok', 'version': __version__}))
        if data.get('command'):
            cmds = data['command'].split(' ')
            cmd = cmds[0]
            if cmd == 'status':
                ret = '; '.join([d['key'] for d in self._tunprocs_map.values()])
                send_package(sock, 0, json.dumps({'status': 'success', 'message': ret}))
            elif cmd == 'kill':
                wkills = set(cmds[1:])
                killeds = set()
                for p, cxt in self._tunprocs_map.items():
                    if 'all' in wkills or cxt['key'] in wkills:
                        self._close_tun_cxt(cxt)
                        killeds.add(cxt['key'])
                send_package(sock, 0, json.dumps({'status': 'success', 'message': '; '.join(killeds)}))
            elif cmd == 'exit':
                send_package(sock, 0, json.dumps({'status': 'success', 'message': 'ok'}))
                exit_system(0)
            else:
                send_package(sock, 0, json.dumps({'status': 'error', 'message': "Unknow %s" % cmd}))
            return
        cxt = {'sock': sock}
        data.setdefault('bind', '0.0.0.0')
        for k in ['bind', 'port']:
            if data.get(k):
                cxt[k] = data[k]
        cxt['key'] = '%s:%s' % (cxt['bind'], cxt['port'])
        self._log('new client version: %s' % data['version'])
        from multiprocessing import Process

        def tunrun():
            t = Tunnel(**cxt)
            t.start()
            # cxt['tun'] = t
            while t._running and self._running:
                time.sleep(3)

        proc = Process(target=tunrun)
        proc.start()
        with self._tunprocs_lock:
            cxt['proc'] = proc
            self._tunprocs_map[proc] = cxt
        return proc

    def _close_tun_cxt(self, cxt):
        sock = cxt.pop('sock', None)
        proc = cxt.pop('proc', None)
        try:
            if sock:
                sock_close(sock)
        except:
            pass
        try:
            if proc:
                proc.terminate()
        except:
            pass

    def _check_tunprocs(self):
        while self._running:
            delps = []
            for p in self._tunprocs_map:
                if not p.is_alive():
                    delps.append(p)
            if delps:
                with self._tunprocs_lock:
                    for p in delps:
                        cxt = self._tunprocs_map[p]
                        self._close_tun_cxt(cxt)
                        self._log('remove process', cxt)
                        del self._tunprocs_map[p]
                self._log('now process count=%d' % len(self._tunprocs_map))
            time.sleep(TIME_FOR_DOG_TIMEOUT / 2 or 1)
            self.feed_dog()

    def _run(self):
        self.start_dog()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('binding %s:%s' % (self.bind, self.port))
            sock.bind((self.bind, self.port), )
            sock.listen(1000)
            self._sock = sock
            self._log('running server %s:%s' % (self.bind, self.port))
        except:
            import traceback
            traceback.print_exc()
            self.stop()
        start_thread(target=self._check_tunprocs)
        while self._running:
            try:
                clt_con, clt_add = self._sock.accept()
                self._log('new client req', clt_con, clt_add)
                try:
                    ret = self._ready(clt_con, clt_add)
                    if not ret:
                        time.sleep(TIME_WAIT_SEND_S)
                        sock_close(clt_con)
                except:
                    import traceback
                    traceback.print_exc()
            except:
                import traceback
                traceback.print_exc()
                self.stop()
        self.stop_dog()


class Client(SockRunable):
    server = '192.168.1.102'
    port = 1990
    passwd = '123'
    proxy_port = 1091
    proxy_bind = '0.0.0.0'

    target_host = '127.0.0.1'
    target_port = 6379
    command = ''
    _client_map = {}

    def _run_con(self, ix, sock):
        while self._running:
            recv = sock_read(sock)
            if len(recv):
                send_package(self._sock, ix, recv)
            else:
                send_package(self._sock, -1 * ix, b'close')
                self._log('a do discon', ix)
                time.sleep(TIME_WAIT_SEND_S)
                sock_close(sock)
                break

    def _add_con(self, ix):
        try:
            self._log('add conn', ix)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('connecting target %s:%s' % (self.target_host, self.target_port))
            sock.connect((self.target_host, self.target_port), )
            self._log('connected target %s:%s' % (self.target_host, self.target_port))
            self._client_map[ix] = {
                'sock': sock,
                'th': start_thread(target=self._run_con, args=[ix, sock])
            }
            return self._client_map[ix]
        except:
            import traceback
            traceback.print_exc()

    def _run_ping(self):
        while self._running:
            send_package(self._sock, 0, b'ping')
            time.sleep(TIME_FOR_PING_S)

    def _run(self):
        self.start_dog()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock = sock
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._log('connecting server %s:%s' % (self.server, self.port))
            sock.connect((self.server, self.port), )
            self._log('connected server %s:%s' % (self.server, self.port))
            self._log('verifying...')
            send_package(sock, 0, json.dumps({'version': __version__, 'command': self.command, 'passwd': self.passwd, 'bind': self.proxy_bind, 'port': self.proxy_port}))
            _, data = read_package(sock)
            ret = json.loads(data)
            if ret['status'] == 'ok':
                self._log('server version V%s, verified!' % ret['version'])
            else:
                self._log('\033[31m%s: %s\033[0m' % (ret['status'], ret['message']))
                raise Exception(ret['message'])
        except:
            import traceback
            traceback.print_exc()
            self.stop()
            return
        self.feed_dog()
        self._ping_th = start_thread(target=self._run_ping)
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
                        # self._log('trans', ix, data[0:20])
                        sock_send(d['sock'], data)
                    else:
                        send_package(sock, -1 * ix, b'')
                elif ix == 0:
                    # message
                    if data == b'ping':
                        send_package(sock, 0, b'pong')
                    elif data == b'pong':
                        self.feed_dog()
                    else:
                        self._log('[Server]\033[31m%s\033[0m' % data.decode())
                        self.stop()
                else:
                    nix = abs(ix)
                    if nix in self._client_map:
                        if data == b'ping':
                            # ping
                            send_package(sock, -1 * ix, b'pong')
                            self.feed_dog()
                        elif not data or data == b'close':
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
    if ':' in s:
        r = s.split(':')
        return r[0], int(r[1])
    elif s:
        return '0.0.0.0', int(s)
    raise Exception(u'%s not a endpoint type!' % s)


def main():
    import time, signal, argparse
    parser = argparse.ArgumentParser(add_help=True)

    parser.add_argument('-t', '--target', help='target endpoint, such as: 127.0.0.1:8080', type=parse_endpoint)
    parser.add_argument('-s', '--server', help='server endpoint, such as: 192.168.1.3:1990', type=parse_endpoint)
    parser.add_argument('-p', '--port', help='server proxy port, such as: 192.168.1.3:1090', type=parse_endpoint)

    parser.add_argument('-b', '--bind', help='the server bind endpoint, such as: 0.0.0.0:1990', type=parse_endpoint)

    parser.add_argument('-e', '--passwd', help='the password, default is empty', type=str, default='')
    parser.add_argument('-c', '--command', help='the method, default is empty', nargs='+', type=str, default='')
    parser.add_argument('-v', '--version', help='show the version %s' % __version__, action='store_true')
    args = parser.parse_args()
    run = None
    if args.version:
        print(__version__)
    elif args.bind:
        # server
        d = {
            'bind': args.bind[0],
            'port': args.bind[1],
            'passwd': args.passwd,
        }
        run = Server(**d)
    elif args.server:
        # client
        d = {
            'server': args.server[0],
            'port': args.server[1],
            'proxy_bind': args.port[0] if args.port else '0.0.0.0',
            'proxy_port': args.port[1] if args.port else 8080,
            'target_host': args.target[0] if args.target else '127.0.0.1',
            'target_port': args.target[1] if args.target else 8080,
            'passwd': args.passwd,
            'command': ' '.join(args.command),
        }
        run = Client(**d)
    else:
        parser.print_help()
        exit_system(-1)

    def stop(a, b):
        print_it('stop')
        run.stop()

    signal.signal(signal.SIGINT, stop)
    if run:
        print_it('---pytunnel V%s---' % __version__)
        run.start()
        while run._running:
            time.sleep(1)
        time.sleep(1)


if __name__ == '__main__':
    main()
