# Use xmake to statically compile xquic

install xmake:

https://xmake.io/#/guide/installation


Tutorial：

https://zhuanlan.zhihu.com/p/603648502

When compiling a static library, please note that:
```
cmake -DGCOV=off -DCMAKE_BUILD_TYPE=Debug -DXQC_ENABLE_TESTING=0 -DXQC_SUPPORT_SENDMMSG_BUILD=1 -DXQC_ENABLE_EVENT_LOG=1 -DXQC_ENABLE_BBR2=1 -DXQC_DISABLE_RENO=0 -DSSL_TYPE=${SSL_TYPE_STR} -DSSL_PATH=${SSL_PATH_STR} -DSSL_INC_PATH=${SSL_INC_PATH_STR} -DSSL_LIB_PATH=${SSL_LIB_PATH_STR} ..
```

- current version: xquic 1.4
- The test case codes in src have modified MAX_BUF_SIZE

