if __name__ == '__main__':
    import socket
    import struct
    import time
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.connect(('localhost', 12345))
        start = time.perf_counter_ns()
        sock.send(struct.pack('!8sBB', b'llpprrvl', 4, 0)+b'Test')
        for i in range(1000):
            sock.send(struct.pack('!8sBB', b'llppstts', 4, 13)+b'Test'+b'Hello, world!')
        sock.send(struct.pack('!8sBB', b'llppdprt', 4, 8)+b'Test'+struct.pack('!Q', time.perf_counter_ns()-start))
