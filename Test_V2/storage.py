# storage.py
import  json
import os.path

Data_File = "data.json"
# 保存所有计划
plans = []
# 下一条计划的 ID
next_id = 1

def load_data():
    global plans
    global next_id

    if not os.path.exists(Data_File):
        return

    with open("data/data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    if plans:
        next_id = max(plans["id"] for plans in plans) + 1

def save_data():
    with open(Data_File, "w",encoding="utf-8") as f:
        json.dump(
            plans,
            f,
            ensure_ascii=False,
            indent=4
        )