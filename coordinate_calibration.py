import cv2
import numpy as np
import serial
import time
import tkinter as tk
from tkinter import messagebox

# ==============================
# 카메라 및 아두이노 설정
# ==============================

CAMERA_INDEX = 1
ARDUINO_PORT = "COM5"
BAUD_RATE = 9600

REAL_WIDTH = 5.55
REAL_HEIGHT = 6.00

PIXELS_PER_CM = 100
W = int(REAL_WIDTH * PIXELS_PER_CM)
H = int(REAL_HEIGHT * PIXELS_PER_CM)

RESET_TIME = 1.0

# ==============================
# 초기 설정
# ==============================

points = []
matrix = None

last_detected_time = 0
object_locked = False
robot_busy = False

# ==============================
# 팝업창 설정
# ==============================

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)

# ==============================
# 마우스 모서리 선택
# ==============================

def mouse_callback(event, x, y, flags, param):
    global points

    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
        points.append((x, y))
        print(f"{len(points)}번째 모서리 선택: ({x}, {y})")


# ==============================
# 아두이노 연결
# ==============================

try:
    arduino = serial.Serial(
        ARDUINO_PORT,
        BAUD_RATE,
        timeout=1
    )

    time.sleep(2)
    arduino.reset_input_buffer()

    print("아두이노 COM5 연결 완료!")

except serial.SerialException as e:
    print("아두이노 연결 실패:", e)
    root.destroy()
    raise SystemExit


# ==============================
# 카메라 연결
# ==============================

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)

if not cap.isOpened():
    print("카메라 연결 실패")
    arduino.close()
    root.destroy()
    raise SystemExit


cv2.namedWindow("Camera Calibration")
cv2.setMouseCallback("Camera Calibration", mouse_callback)

print("네모칸의 네 모서리를 순서대로 클릭하세요.")
print("왼쪽 위 -> 오른쪽 위 -> 오른쪽 아래 -> 왼쪽 아래")
print("4개를 클릭한 다음 C를 누르세요.")


# ==============================
# 메인 프로그램
# ==============================

try:
    while True:

        ret, frame = cap.read()

        if not ret:
            print("영상 수신 실패")
            break

        # ==============================
        # 아두이노 동작 완료 신호 확인
        # ==============================

        if arduino.in_waiting > 0:

            response = arduino.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if response == "DONE":

                robot_busy = False

                print("로봇팔 분류 동작 완료!")

                # 다음 실험 준비 팝업
                messagebox.showinfo(
                    "실험 완료",
                    "물체 분류가 완료되었습니다.\n\n"
                    "다음 실험을 준비한 뒤\n"
                    "'확인'을 눌러주세요.",
                    parent=root
                )

                print("다음 실험 준비 중...")

        display = frame.copy()

        # 모서리 표시
        for i, point in enumerate(points):

            cv2.circle(
                display,
                point,
                6,
                (0, 255, 0),
                -1
            )

            cv2.putText(
                display,
                str(i + 1),
                (point[0] + 10, point[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        cv2.putText(
            display,
            "Click corners: TL -> TR -> BR -> BL",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 0, 0),
            2
        )

        cv2.putText(
            display,
            "C: calibrate / R: reset / ESC: quit",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 0, 0),
            2
        )

        cv2.imshow("Camera Calibration", display)

        # ==============================
        # 좌표 보정 완료 후 색상 인식
        # ==============================

        if matrix is not None:

            warped = cv2.warpPerspective(
                frame,
                matrix,
                (W, H)
            )

            hsv = cv2.cvtColor(
                warped,
                cv2.COLOR_BGR2HSV
            )

            # 빨간색 인식
            red1 = cv2.inRange(
                hsv,
                (0, 100, 100),
                (10, 255, 255)
            )

            red2 = cv2.inRange(
                hsv,
                (160, 100, 100),
                (180, 255, 255)
            )

            red = red1 | red2

            # 노란색 인식
            yellow = cv2.inRange(
                hsv,
                (20, 100, 100),
                (35, 255, 255)
            )

            colors = [
                ("RED", red, (0, 0, 255), "RIGHT", b'R'),
                ("YELLOW", yellow, (0, 255, 255), "LEFT", b'Y')
            ]

            # 가운데 선
            cv2.line(
                warped,
                (W // 2, 0),
                (W // 2, H),
                (255, 255, 255),
                1
            )

            detected_objects = []

            for name, mask, color, direction, command in colors:

                contours, _ = cv2.findContours(
                    mask,
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )

                for contour in contours:

                    area = cv2.contourArea(contour)

                    if area < 500:
                        continue

                    moments = cv2.moments(contour)

                    if moments["m00"] == 0:
                        continue

                    cx = int(moments["m10"] / moments["m00"])
                    cy = int(moments["m01"] / moments["m00"])

                    detected_objects.append(
                        (area, name, color, direction, command, cx, cy)
                    )

            # ==============================
            # 물체 인식 및 명령 전송
            # ==============================

            if detected_objects:

                last_detected_time = time.time()

                detected_objects.sort(
                    key=lambda item: item[0],
                    reverse=True
                )

                area, name, color, direction, command, cx, cy = detected_objects[0]

                x_cm = cx / PIXELS_PER_CM
                y_cm = cy / PIXELS_PER_CM

                robot_x = x_cm - (REAL_WIDTH / 2)
                robot_y = 15.4 + (REAL_HEIGHT / 2 - y_cm) * 0.633

                cv2.circle(
                    warped,
                    (cx, cy),
                    5,
                    color,
                    -1
                )

                cv2.putText(
                    warped,
                    f"{name} -> {direction}",
                    (max(5, cx - 30), max(20, cy - 25)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )

                cv2.putText(
                    warped,
                    f"X={x_cm:.2f} Y={y_cm:.2f} cm",
                    (max(5, cx - 30), min(H - 10, cy + 25)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )

                # 한 번에 한 물체만 처리
                if not object_locked and not robot_busy:

                    arduino.write(command)
                    arduino.flush()

                    object_locked = True
                    robot_busy = True

                    print("========================")
                    print(f"{name} 인식!")
                    print(f"Robot X={robot_x:.2f} cm")
                    print(f"Robot Y={robot_y:.2f} cm")
                    print(f"명령 전송: {command.decode()}")
                    print(f"분류 방향: {direction}")
                    print("========================")

            else:

                # 물체가 사라진 뒤 다음 실험 허용
                if (
                    object_locked
                    and not robot_busy
                    and time.time() - last_detected_time > RESET_TIME
                ):

                    object_locked = False

                    print("다음 물체 인식 대기 중...")

            cv2.imshow("Calibrated Workspace", warped)

        # ==============================
        # 키 입력
        # ==============================

        key = cv2.waitKey(1) & 0xFF

        if key == ord('c'):

            if len(points) == 4:

                src = np.float32(points)

                dst = np.float32([
                    [0, 0],
                    [W - 1, 0],
                    [W - 1, H - 1],
                    [0, H - 1]
                ])

                matrix = cv2.getPerspectiveTransform(
                    src,
                    dst
                )

                print("좌표 보정 완료!")
                print("실제 작업 영역: 5.55cm x 6.00cm")
                print("빨간색 -> 오른쪽")
                print("노란색 -> 왼쪽")

            else:
                print("모서리 4개를 먼저 클릭하세요.")

        elif key == ord('r'):

            if not robot_busy:
                points = []
                matrix = None
                object_locked = False

                print("좌표 설정 초기화 완료.")
            else:
                print("로봇팔 동작 중에는 초기화할 수 없습니다.")

        elif key == 27:
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    arduino.close()
    root.destroy()

    print("카메라 및 아두이노 연결 종료")