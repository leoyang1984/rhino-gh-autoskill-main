import Grasshopper
import json

# 诊断脚本 — 不写文件，只打印信息

server = Grasshopper.Instances.ComponentServer

proxies = list(server.ObjectProxies)
print(f"ObjectProxies 总数: {len(proxies)}")

if len(proxies) == 0:
    print("⚠️ ObjectProxies 为空，ComponentServer 可能未初始化")
else:
    # 打印前5个，看数据结构
    count = 0
    for proxy in proxies:
        try:
            print(f"---")
            print(f"  Guid: {proxy.Guid}")
            print(f"  Obsolete: {proxy.Obsolete}")
            print(f"  Hidden: {getattr(proxy, 'Hidden', 'N/A')}")
            print(f"  Name: {proxy.Desc.Name}")
            print(f"  Category: {proxy.Desc.Category}")

            obj = proxy.CreateInstance()
            if obj is None:
                print(f"  CreateInstance: None")
                continue

            if hasattr(obj, "Params") and obj.Params is not None:
                inputs = [p.Name for p in obj.Params.Input]
                outputs = [p.Name for p in obj.Params.Output]
                print(f"  Inputs: {inputs}")
                print(f"  Outputs: {outputs}")
            else:
                print(f"  Params: None or missing")

            count += 1
            if count >= 5:
                break
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

print(f"\n前5个组件读取完毕")
