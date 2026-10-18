# -*- coding: utf-8 -*-
"""本地 HTTP CONNECT 中继：把 github.com:443 的流量送到一个可达的边缘 IP。

背景：本机 DNS 把 github.com 解析到 20.205.243.166（亚太节点），该 IP 被重置；
而 140.82.112.x 等美国节点是通的。hosts 文件需要管理员权限，改不了。

做法：git 通过 `http.proxy` 连到这个本地中继，中继把 CONNECT 的目标忽略掉，
固定转发到指定 IP。TLS 仍然是 git 与 github.com 端到端完成的（中继只搬字节，
不解密、不改写），所以证书校验照常生效。

只监听 127.0.0.1，用完即关。

    python tools/gh_relay.py --port 18080 --target 140.82.112.3:443
"""
import argparse
import socket
import threading
import sys

BUFSIZE = 65536


def pipe(src, dst, tag=""):
    try:
        while True:
            data = src.recv(BUFSIZE)
            if not data:
                break
            dst.sendall(data)
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client, target_host, target_port, log):
    try:
        # 读 CONNECT 请求头（到空行为止）
        header = b""
        client.settimeout(15)
        while b"\r\n\r\n" not in header:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            header += chunk
            if len(header) > 65536:
                client.close()
                return

        first_line = header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        log.write("CONNECT: %s -> %s:%d\n" % (first_line, target_host, target_port))
        log.flush()

        upstream = socket.create_connection((target_host, target_port), timeout=20)
        client.settimeout(None)
        upstream.settimeout(None)
        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        t = threading.Thread(target=pipe, args=(client, upstream, "up"), daemon=True)
        t.start()
        pipe(upstream, client, "down")
        t.join(timeout=5)
    except Exception as e:
        log.write("ERR: %r\n" % (e,))
        log.flush()
        try:
            client.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--target", default="140.82.112.3:443")
    ap.add_argument("--log", default="relay.log")
    args = ap.parse_args()

    host, port = args.target.rsplit(":", 1)
    port = int(port)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(64)

    with open(args.log, "a", encoding="utf-8") as log:
        log.write("relay listening on 127.0.0.1:%d -> %s:%d\n"
                  % (args.port, host, port))
        log.flush()
        print("relay 127.0.0.1:%d -> %s:%d" % (args.port, host, port), flush=True)
        try:
            while True:
                client, _ = srv.accept()
                threading.Thread(target=handle,
                                 args=(client, host, port, log),
                                 daemon=True).start()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
