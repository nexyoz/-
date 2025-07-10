# main_integrated.py - Vision Board 视觉按键识别与串口发送程序
import sensor
import image
import time
import pyb

# ====================================================================
# --- 第1部分：按键映射数据（请替换为实际校准数据）---
# ====================================================================
keymap_data = [
    {'center': (179,161), 'rect': (174, 152, 30, 30), 'key': 'J'},
    {'center': (143,150), 'rect': (138, 141, 30, 30), 'key': 'H'},
    {'center': (227,149), 'rect': (222, 140, 30, 30), 'key': 'L'},
    {'center': (62,120), 'rect': (57, 111, 30, 30), 'key': 'R'},
    {'center': (120,150), 'rect': (115, 141, 30, 30), 'key': 'G'},
    {'center': (5,185), 'rect': (0, 176, 30, 30), 'key': 'Z'},
    {'center': (50,151), 'rect': (45, 146, 30, 30), 'key': 'D'},
    {'center': (160,191), 'rect': (110, 206, 100, 30), 'key': 'SPACE'},
    {'center': (62, 113), 'rect': (57,104,30, 30), 'key': '-'},
    {'center': (222, 99), 'rect': (217, 90, 10, 17), 'key': 'BACK'},
    ]

# ====================================================================
# --- 第2部分：主程序逻辑（优化版）---
# ====================================================================

# --- 配置参数 ---
BLOB_THRESHOLD = (10, 255)       # 红外斑点阈值（根据实际环境调整）
DEBOUNCE_TIME = 200             # 按键去抖时间(ms)
MIN_BLOB_PIXELS = 50            # 最小斑点像素数
COORD_PRINT_INTERVAL = 2000     # 坐标打印间隔(ms)

# --- 初始化摄像头 ---
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)  # 320x240分辨率
sensor.skip_frames(time=2000)      # 等待设置生效
# 固定曝光和增益以提高识别稳定性
sensor.set_auto_gain(False, gain_db=12)
sensor.set_auto_exposure(False, exposure_us=1200)

# --- 初始化串口（根据Vision Board实际串口调整）---
# 假设使用UART2，波特率115200
uart_to_mcu = pyb.UART(9, 115200)

# --- 状态变量 ---
last_pressed_key = None          # 上一次按下的按键
last_key_time = 0                # 上次按键时间（去抖用）
last_center_coords = None        # 上一次识别的中心坐标
last_print_time = 0              # 上次打印坐标的时间
led_blue = pyb.LED(3)            # 蓝色LED指示灯
debug_mode = True                # 调试模式开关

# 调试用时钟
clock = time.clock()

print("--- Vision Keyboard System Started ---")
print(f"Keymap loaded: {len(keymap_data)} keys")
print("Waiting for input...")

# --- 主循环 ---
while True:
    clock.tick()
    img = sensor.snapshot()

    # 查找红外斑点
    blobs = img.find_blobs([BLOB_THRESHOLD],
                          pixels_threshold=MIN_BLOB_PIXELS,
                          area_threshold=MIN_BLOB_PIXELS,
                          merge=True)

    current_key_found = None
    current_center_coords = None  # 当前识别区域的中心坐标
    main_blob = None

    if blobs:
        # 选择最大的斑点
        main_blob = max(blobs, key=lambda b: b.pixels())
        cx, cy = main_blob.cx(), main_blob.cy()

        # 绘制斑点调试信息
        img.draw_rectangle(main_blob.rect(), color=128)
        img.draw_cross(cx, cy, color=128)

        # 检测按键映射
        for key_info in keymap_data:
            rect = key_info["rect"]
            key = key_info["key"]
            center = key_info["center"]  # 获取该区域的中心坐标

            if (cx > rect[0] and cx < rect[0] + rect[2] and
                cy > rect[1] and cy < rect[1] + rect[3]):

                if key != "NULL":
                    current_key_found = key
                    current_center_coords = center  # 记录当前识别区域的中心坐标
                    # 高亮显示当前按键
                    img.draw_rectangle(rect, color=255, thickness=2)
                break

    # 更新当前中心坐标（即使未识别到按键也更新）
    if blobs and current_center_coords:
        last_center_coords = current_center_coords
    elif not blobs:
        last_center_coords = None  # 没有检测到斑点时，中心坐标为None

    # --- 按键状态机（带去抖处理）---
    current_time = time.ticks_ms()
    if current_key_found != last_pressed_key or (current_key_found and last_pressed_key):
        # 去抖检查
        if current_key_found and time.ticks_diff(current_time, last_key_time) < DEBOUNCE_TIME:
            current_key_found = None

        if current_key_found != last_pressed_key:
            # 按键状态变化时更新LED
            led_blue.on() if current_key_found else led_blue.off()

            # 发送按键释放命令
            if last_pressed_key:
                release_cmd = f"U_{last_pressed_key}\n"
                uart_to_mcu.write(release_cmd)
                if debug_mode:
                    print(f"[RELEASE] {last_pressed_key}")

            # 发送按键按下命令并打印中心坐标
            if current_key_found:
                press_cmd = f"D_{current_key_found}\n"
                uart_to_mcu.write(press_cmd)
                if debug_mode:
                    print(f"[PRESS] {current_key_found}")
                    # 打印识别区域的中心坐标
                    print(f"[CENTER] 识别区域中心坐标: {current_center_coords}")

            last_pressed_key = current_key_found
            last_key_time = current_time

    # --- 每2秒定时打印坐标 ---
    if time.ticks_diff(current_time, last_print_time) >= COORD_PRINT_INTERVAL:
        if last_center_coords:
            print(f"[定时] 中心坐标: {last_center_coords}")
        else:
            print("[定时] 未检测到有效按键区域")
        last_print_time = current_time

    # --- 显示调试信息 ---
    fps = clock.fps()
    key_status = last_pressed_key if last_pressed_key else "None"
    # 在调试信息中添加中心坐标显示
    center_info = f"Center: {last_center_coords}" if last_center_coords else "Center: None"
    debug_info = f"FPS: {fps:.1f}\nKey: {key_status}\n{center_info}"

    img.draw_string(5, 5, debug_info, color=255, scale=2)

    # 控制CPU占用率
    time.sleep_ms(10)
