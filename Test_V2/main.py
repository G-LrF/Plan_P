import service
import storage


# ===== 主菜单循环 =====
def main():
    storage.load_data()

    menu = { #映射
        "1": service.create_plan,
        "2": service.show_plans,
        "3": service.update_plan,
        "4": service.delete_plan,
        "5": service.finish_plan,
        "6": service.search_plan,
        "7": service.stat_plan
    }
    while True:
        print("\n====== 计划管理系统 ======")
        print("1. 创建计划")
        print("2. 查看计划")
        print("3. 修改计划")
        print("4. 删除计划")
        print("5. 完成计划")
        print("6. 搜索计划")
        print("7. 统计计划")
        print("0. 退出系统")
        choice = input("请输入操作编号：").strip()
        if choice == "0":# 选 0 就跳出循环
            print("再见！")
            break
        if choice in menu:# 输入的是 1~7 之间
            menu[choice]()# 调用对应的函数（函数名后面加括号 = 执行它）
        else:# 输入了别的数字
            print("输入无效，请重新选择！")

if __name__ == "__main__":
    main()