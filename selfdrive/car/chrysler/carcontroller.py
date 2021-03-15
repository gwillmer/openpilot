from selfdrive.car import apply_toyota_steer_torque_limits
from selfdrive.car.chrysler.chryslercan import create_lkas_hud, create_lkas_command, \
                                               create_wheel_buttons
from selfdrive.car.chrysler.values import CAR, CarControllerParams
from opendbc.can.packer import CANPacker
from selfdrive.car.interfaces import GearShifter


class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.apply_steer_last = 0
    self.ccframe = 0
    self.prev_frame = -1
    self.hud_count = 0
    self.car_fingerprint = CP.carFingerprint
    self.steer_rate_limited = False
    self.timer = 0
    self.steerErrorMod = False
    self.steer_type = int(0)

    self.packer = CANPacker(dbc_name)

  def update(self, enabled, CS, actuators, pcm_cancel_cmd, hud_alert):
    # this seems needed to avoid steering faults and to force the sync with the EPS counter
    frame = CS.lkas_counter
    if self.prev_frame == frame:
      return []

    # *** compute control surfaces ***

    spoof_speed = 0.

    if spoof_speed == 65.:
      wp_type = int(1)
    elif spoof_speed == 0.:
      wp_type = int(2)
    else:
      wp_type = int(0)

    if enabled:
      if self.timer < 99 and wp_type == 1 and CS.out.vEgo < 65:
        self.timer += 1
      else:
        self.timer = 99
    else:
      self.timer = 0

    lkas_active = self.timer == 99

# steer torque
    new_steer = actuators.steer * CarControllerParams.STEER_MAX
    apply_steer = apply_toyota_steer_torque_limits(new_steer, self.apply_steer_last,
                                                   CS.out.steeringTorqueEps, CarControllerParams)
    if not lkas_active:
      apply_steer = 0

    self.steer_rate_limited = new_steer != apply_steer

    self.apply_steer_last = apply_steer

    if CS.out.standstill:
      self.steer_type = wp_type

    if wp_type != 2:
      self.steerErrorMod = CS.steerError
      self.steer_type = int(0)
    elif CS.apaFault:
      self.steer_type = int(0)

    self.apaActive = CS.apasteerOn and self.steer_type == 2

    can_sends = []

    #*** control msgs ***

   # if pcm_cancel_cmd:
   #   # TODO: would be better to start from frame_2b3
   #   new_msg = create_wheel_buttons(self.packer, self.ccframe, cancel=True)
   #   can_sends.append(new_msg)

    # LKAS_HEARTBIT is forwarded by Panda so no need to send it here.
    # frame is 100Hz (0.01s period)
    if (self.ccframe % 2 == 0):  # 0.25s period
      if (CS.lkas_car_model != -1):
        new_msg = create_lkas_hud(
            self.packer, CS.out.gearShifter, self.apaActive, CS.apaFault, hud_alert, lkas_active,
            self.hud_count, CS.lkas_car_model, self.steer_type)
        can_sends.append(new_msg)
        self.hud_count += 1

    new_msg = create_lkas_command(self.packer, int(apply_steer), lkas_active, frame)
    can_sends.append(new_msg)

    self.ccframe += 1
    self.prev_frame = frame

    return can_sends
