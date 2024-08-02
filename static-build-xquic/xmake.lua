add_rules("mode.debug", "mode.release")

target("client")
    set_kind("binary")
    add_includedirs("./include") -- 头文件目录
    add_linkdirs("./lib") -- 库目录
    add_links("xquic-static", "event", "ssl", "crypto") -- 链接库
    add_syslinks("pthread") -- 链接系统提供的库
    add_files("src/test_client.c")

target("server")
    set_kind("binary")
    add_includedirs("./include") -- 头文件目录
    add_linkdirs("./lib") -- 库目录
    add_links("xquic-static", "event", "ssl", "crypto") -- 链接库
    add_syslinks("pthread") -- 链接系统提供的库
    add_files("src/test_server.c")
