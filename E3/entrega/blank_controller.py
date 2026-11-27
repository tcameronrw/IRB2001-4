from controller import Robot
import numpy as np
import cv2
from perception import perception
from action import control, obtener_fase

robot = Robot()
TIMESTEP = int(robot.getBasicTimeStep())
motor_izq = robot.getDevice("left wheel motor")
motor_der = robot.getDevice("right wheel motor")

for motor in (motor_izq, motor_der):
    motor.setPosition(float("inf"))
    motor.setVelocity(0.0)

dt = TIMESTEP / 1000.0

max_izq = motor_izq.getMaxVelocity()
max_der = motor_der.getMaxVelocity()


control(None, reset=True)

try:
    while robot.step(TIMESTEP) != -1:
        try:
            while robot.step(TIMESTEP) != -1:
                # Check if there is a new image from the Supervisor
                with open('../referee_supervisor/raw_files/camera_b.raw', 'rb') as f:
                    raw_data = f.read()
                # Convert raw data to a NumPy array
                img = np.frombuffer(raw_data, dtype=np.uint8).copy()
                img = img.reshape((720, 1280, 3))
                img = img[:, :, :3]
        
                estado = perception(img)
                u, v = control(estado, dt=dt)
        
                velocidad_izq = float(np.clip(u + v, -max_izq, max_izq))
                velocidad_der = float(np.clip(u - v, -max_der, max_der))
                motor_izq.setVelocity(velocidad_izq)
                motor_der.setVelocity(velocidad_der)
        
                diagnostico = obtener_fase()
                if estado is not None:
                    d, th = estado
                    diagnostico += f" | d={d:.1f}px | theta={th:.1f}deg"
                else:
                    diagnostico += " | sin deteccion"
                cv2.putText(img, diagnostico, (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                cv2.imshow("E3 - Robot", img)
                cv2.waitKey(1)

        except (FileNotFoundError, OSError, ValueError):
            control(None, dt=dt)
            motor_izq.setVelocity(0.0)
            motor_der.setVelocity(0.0)
            continue
finally:
    motor_izq.setVelocity(0.0)
    motor_der.setVelocity(0.0)
    cv2.destroyAllWindows()