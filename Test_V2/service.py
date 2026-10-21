import datetime
import storage

#创建任务
def create_plan():
    title = input("请输入计划标题：").strip()
    content = input('输入计划内容：').strip()
    if not title:
        print("标题不能空")
        return
    #后续plan改为sql语句导入数据库
    plan = {
        "id":storage.next_id,
        "title":title,
        "content":content,
        "status":0, #0未完成 1代表完成
        "create_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    storage.plans.append(plan)
    storage.next_id += 1
    storage.save_data()

    print(f"计划【{title}】创建成功")

#查看计划
def show_plans():
    if not storage.plans:
        print("无任何计划")
        return

    print("-" * 50)

    for p in storage.plans:
        status = "✅  已完成" if p["status"] == 1 else "未完成"

        print(
            f"编号:{p['id']}|"
            f"title:{p['title']}|"
            f"status:{status}|"
            f"content:{p['content']}|"
            f"create_time:{p['create_time']}"
        )

    print("-" * 50)

#3.修改计划 ps：后续数据更新改为sql数据库更新 在后续加入redis消息队列
def update_plan():
    pid = input("请输入要修改的计划编号:").strip()

    for p in storage.plans :
        if str(p["id"]) == pid:
            #     new_title = input(f'新标题（原：{p["title"]},直接回车不改：').strip()
            #     new_content = input(f'新标题（原：{p["content"]},直接回车不改：').strip()
            # #45-48能不能换一种写法
            # if new_title:  # 如果用户输入了新标题（非空）
            #     p["title"] = new_title # 就更新
            # if new_content :
            #     p["content"] = new_content
            new_title = input(
                f'新标题（原：{p["title"]}，直接回车不改）：'
            ).strip()
            p["title"] = new_title or p["title"]

            new_content = input(
                f'新内容（原：{p["content"]}，直接回车不改）：'
                                ).strip()
            p["content"] = new_content or p["content"]

            storage.save_data()
            print("修改成功")
            return

    print("没找到该编号的计划")

#4 删除 如同3
def delete_plan():
    pid = input("请输入要删除的计划编号:").strip()

    for p in storage.plans:
        if str(p["id"]) == pid :
            storage.plans.remove(p)
            storage.save_data()
            print("删除成功")
            return
    print("没找到该编号的计划")


#5 完成计划（状态更改)
def finish_plan():
    pid = input("输入标记完成的计划编号：").strip()

    for p in storage.plans:
        if str(p["id"]) == pid:
            p["status"] = 1
            storage.save_data()
            print(f'计划【{p["title"]}】已完成！')
            return

    print("没找到该编号的计划！")

#6  搜索计划 模糊搜索
def search_plan():
    keyword = input("请输入要搜索的关键字：").strip()
    result = [p for p in storage.plans if keyword in p["title"]]
    if not result:
        print("没有匹配的计划！")
        return
    for p in  result:
        status = "已完成" if p["status"] == 1 else "未完成"
        print(f'编号：{p["id"]}|标题:{p["title"]}|状态:{status}')


#7 统计计划
def stat_plan():
    total = len(storage.plans)
    done = len([p for p in storage.plans if p["status"]==1])
    # done_plans = []
    #
    # for p in plans:
    #     if p["status"] == 1:
    #         done_plans.append(p)
    #
    # done = len(done_plans)
    undone = total - done
    print(f"计划总数：{total}")
    print(f"已完成：{done}")
    print(f"未完成：{undone}")
    if total > 0:
            print(f"完成率：{done / total * 100:.1f}%")
