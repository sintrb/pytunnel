pytunnel
===============
A TCP tunnel server/client by Python.

Install
===============
```
 pip install pytunnel
```

Useage
===============
If you want local computer port 8080 can be access through server(IP:192.168.1.102) port 1090

Setp1. Run the following command at server computer:

```bash
python -m pytunnel --bind 0.0.0.0:1990
```

It will start a tunnel server at port 1990.

Setp2. Run the following command at local computer:
```bash
python -m pytunnel --port 1090 --target 127.0.0.1:8080 --server 192.168.1.102:1990
```

It will make a tunnel with 192.168.1.102:1090 and 127.0.0.1:8080.

Now, you can open 192.168.1.102:1090 to access the local computer port 8080.


[Click to view more information!](https://github.com/sintrb/pytunnel)