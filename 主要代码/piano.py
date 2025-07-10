# ====================================================================
# --- 第1部分：导入库和钢琴键映射数据 ---
# ====================================================================
import sensor
import image
import time
import pyb

# --------------------------------------------------------------------
# 钢琴键映射表 (Piano Keymap Data)
#
# 为一个八度的钢琴键（从C4到E5）定义了映射区域。
# 坐标系基于 320x240 (QVGA) 的图像分辨率。
#
# - 'key': 音符名称 (例如: 'C4', 'CS4' 代表 C#4)
# - 'rect': (x, y, 宽, 高) 定义了琴键的检测区域
# - 'center': (cx, cy) 琴键区域的中心点，用于校准或调试
# --------------------------------------------------------------------

# --- 白键 (White Keys) ---
# 尺寸较大，位于图像下方
white_keys = [
    {'center': (50, 190), 'rect': (40, 150, 20, 80), 'key': 'C4'},
    {'center': (70, 190), 'rect': (60, 150, 20, 80), 'key': 'D4'},
    {'center': (90, 190), 'rect': (80, 150, 20, 80), 'key': 'E4'},
    {'center': (110, 190), 'rect': (100, 150, 20, 80), 'key': 'F4'},
    {'center': (130, 190), 'rect': (120, 150, 20, 80), 'key': 'G4'},
    {'center': (150, 190), 'rect': (140, 150, 20, 80), 'key': 'A4'},
    {'center': (170, 190), 'rect': (160, 150, 20, 80), 'key': 'B4'},
    {'center': (190, 190), 'rect': (180, 150, 20, 80), 'key': 'C5'},
    {'center': (210, 190), 'rect': (200, 150, 20, 80), 'key': 'D5'},
    {'center': (230, 190), 'rect': (220, 150, 20, 80), 'key': 'E5'},
]

# --- 黑键 (Black Keys) ---
# 尺寸较小，位于白键上方和之间
# 'CS4' 代表 C sharp 4 (C#4), 'DS4' 代表 D sharp 4 (D#4), etc.
black_keys = [
    # {'center': (原x-20, y), 'rect': (原x-20, y, 宽, 高), 'key': '...'},
    {'center': (40, 125), 'rect': (33, 100, 14, 50), 'key': 'CS4'},
    {'center': (60, 125), 'rect': (53, 100, 14, 50), 'key': 'DS4'},
    # E4和F4之间没有黑键
    {'center': (100, 125), 'rect': (93, 100, 14, 50), 'key': 'FS4'},
    {'center': (120, 125), 'rect': (113, 100, 14, 50), 'key': 'GS4'},
    {'center': (140, 125), 'rect': (133, 100, 14, 50), 'key': 'AS4'},
    # B4和C5之间没有黑键
    {'center': (180, 125), 'rect': (173, 100, 14, 50), 'key': 'CS5'},
    {'center': (200, 125), 'rect': (193, 100, 14, 50), 'key': 'DS5'},
]

# --- 合并所有琴键 ---
# 将黑键放在前面，因为它们在视觉上位于上层。
# 当手指按在黑键和白键的重叠区域时，优先检测为黑键。
pianokey_map_data = black_keys + white_keys


# ====================================================================
# --- 第2部分：主程序逻辑 (与原代码完全相同) ---
# ====================================================================

# --- 配置 ---
BLOB_THRESHOLD = (5, 255) # 根据你的实际红外环境调整此阈值

# --- 初始化摄像头 ---
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA) # 320x240
sensor.skip_frames(time=2000)
# 固定曝光和增益对稳定识别至关重要
sensor.set_auto_gain(False, gain_db=10)
sensor.set_auto_exposure(False, exposure_us=1000)

# --- 初始化与RT-Thread主控通信的串口 ---
# 在RT-Thread Vision Board上，OpenMV通过其UART(9)与主控的uart4连接
uart_to_mcu = pyb.UART(9, 115200)

# --- 状态变量 ---
last_pressed_key = None
led_blue = pyb.LED(3)

# 调试信息用的时钟，用于计算帧率FPS
clock = time.clock()

print("--- Virtual Piano Script ---")
print("All code is running from RAM.")
print("Piano keymap data has been loaded internally.")

# --- 主循环 ---
while True:
    clock.tick() # 更新时钟
    img = sensor.snapshot()

    blobs = img.find_blobs([BLOB_THRESHOLD], pixels_threshold=50, area_threshold=50, merge=True)

    current_key_found = None

    if blobs:
        main_blob = max(blobs, key=lambda b: b.pixels())
        cx = main_blob.cx()
        cy = main_blob.cy()

        # 在屏幕上绘制检测到的斑点
        img.draw_rectangle(main_blob.rect(), color=128)
        img.draw_cross(cx, cy, color=128)

        # 遍历校准好的钢琴键映射表
        for key_info in pianokey_map_data:
            key_rect = key_info["rect"]
            if (cx > key_rect[0] and cx < key_rect[0] + key_rect[2] and
                cy > key_rect[1] and cy < key_rect[1] + key_rect[3]):

                # 这里假设所有定义的琴键都是有效的，不像键盘有'NULL'键
                current_key_found = key_info["key"]
                # 高亮显示被按下的键
                img.draw_rectangle(key_rect, color=200, thickness=2)
                break

    # --- 状态机与串口发送逻辑 ---
    if current_key_found != last_pressed_key:
        led_blue.on() if current_key_found else led_blue.off()

        if last_pressed_key:
            # 发送音符关闭 (Note Off) 指令
            release_command = f"U_{last_pressed_key}\n" # 'U' for Up
            uart_to_mcu.write(release_command)
            print(f"Note Released: {last_pressed_key}, Sent: {release_command.strip()}")

        if current_key_found:
            # 发送音符开启 (Note On) 指令
            press_command = f"D_{current_key_found}\n" # 'D' for Down
            uart_to_mcu.write(press_command)
            print(f"Note Pressed:  {current_key_found}, Sent: {press_command.strip()}")

        last_pressed_key = current_key_found

    # 在屏幕左上角显示帧率(FPS)和当前按下的音符
    fps = clock.fps()
    display_text = f"FPS: {fps:.2f}\nNote: {last_pressed_key if last_pressed_key else 'None'}"
    img.draw_string(5, 5, display_text, color=255, scale=2, mono_space=False)

    # 延时以降低CPU占用率
    time.sleep_ms(30)
