# 使用xmake静态编译xquic

安装xmake:

https://xmake.io/#/guide/installation


教程：

https://zhuanlan.zhihu.com/p/603648502

编译静态库时注意,用下面：
```
cmake -DGCOV=off -DCMAKE_BUILD_TYPE=Debug -DXQC_ENABLE_TESTING=0 -DXQC_SUPPORT_SENDMMSG_BUILD=1 -DXQC_ENABLE_EVENT_LOG=1 -DXQC_ENABLE_BBR2=1 -DXQC_DISABLE_RENO=0 -DSSL_TYPE=${SSL_TYPE_STR} -DSSL_PATH=${SSL_PATH_STR} -DSSL_INC_PATH=${SSL_INC_PATH_STR} -DSSL_LIB_PATH=${SSL_LIB_PATH_STR} ..
```

- 当前版本: xquic 1.4
- src中的测试用例代码均修改了MAX_BUF_SIZE

