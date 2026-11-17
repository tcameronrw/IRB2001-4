from simple_pid import PID

kp_d = 1.0
kd_d = 0.1
ki_d = 0.05

kp_th = 1.0
kd_th = 0.1
ki_th = 0.05



pid_d = PID(kp_d, ki_d, kd_d, setpoint=1)
pid_th = PID(kp_th, ki_th, kd_th, setpoint=1)

def control(state, reset):

    #state = [d, theta]

    if reset:
        pid_d.reset()
        pid_th.reset()
        return 0.0, 0.0  
    if not state:
        return 0.0, 0.0

    d = state[0]
    theta = state[1]

    u = d*pid_d
    v = theta*pid_th

    return u, v