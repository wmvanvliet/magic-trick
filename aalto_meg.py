"""Interface between python (psychopy) and the MEG hardware at Aalto's MEG core.

Authors: Marijn van Vliet (w.m.vanvliet@gmail.com)
         Laura Rautiainen (laurasofia.rautiainen@gmail.com)
"""

import random

import nidaqmx
from nidaqmx.constants import (
    READ_ALL_AVAILABLE,
    WAIT_INFINITELY,
    AcquisitionType,
    LineGrouping,
)
from nidaqmx.errors import DaqReadError
from psychopy import core, parallel

# These constants are specific to the stimulus-pc in the MEG lab
LPT1_ADDRESS = 0x6FF8  # address of LPT1 port
LEFT_BUTTON_LINE = 25  # left response pad is on line 25 (zero indexed)
RIGHT_BUTTON_LINE = 26  # right response pad in on line 26 (zero indexed)
RESPONSE_PAD_CHANNEL1_LINE = 17  # right index finger
RESPONSE_PAD_CHANNEL2_LINE = 18  # right middle finger
RESPONSE_PAD_CHANNEL3_LINE = 19  # right ring finger
RESPONSE_PAD_CHANNEL4_LINE = 20  # right pinky
RESPONSE_PAD_CHANNEL5_LINE = 21  # left index finger
RESPONSE_PAD_CHANNEL6_LINE = 22  # left middle finger
RESPONSE_PAD_CHANNEL7_LINE = 23  # left ring finger
RESPONSE_PAD_CHANNEL8_LINE = 24  # left pinky


class AaltoMEG:
    """Interface to the MEG hardware at Aalto's MEG core.

    Parameters
    ----------
    fake : bool
        When this is set to ``True``, don't connect to any hardware but "fake" all the
        responses. This is useful for testing things on your own machine.

    """

    def __init__(self, fake=False):
        self.fake = fake
        if fake:
            # Don't connect to actual hardware
            return

        self.parallel_port = parallel.ParallelPort(address=LPT1_ADDRESS)
        self.parallel_port.setData(0)

    def send_trigger_code(self, code):
        """Send a trigger code to the MEG status channel.

        The trigger code ends up in the STI101 channel, which will jump from 0 to the
        desired code, stay there for 3 ms (about 3 samples) and then jump back to 0.
        For this reason, sending a trigger code of `0` is not possible. Also, the
        maximum possible trigger code is 127.

        Parameters
        ----------
        code : int
            Trigger code to send. The code needs to be in the range 1-127.

        """
        if not (1 <= code <= 127):
            raise ValueError("Trigger codes need to be in the range 1-127.")

        if self.fake:
            # Don't actually send anything, but pretend we do
            core.wait(0.003)
            return

        self.parallel_port.setData(code)
        core.wait(0.003)
        self.parallel_port.setData(0)

    def wait_for_button_press(self, timeout=None):
        """Wait until the participant has pressed one of the left/right buttons.

        Use this function to interface with the big white response "button" pads that
        have a single light sensor.

        Parameters
        ----------
        timeout : float
            The number of seconds to wait for a response. When this time has elapsed,
            this function returns ``None`` indicating no response was received. You can
            specify ``timeout=None`` to wait indefinitely.

        Returns
        -------
        response : str | None
            "left": Left button
            "right": Right button
            None : No response

        """
        if self.fake:
            # Fake a random button press.
            core.wait(0.5 + 0.2 * random.random())
            return random.choice(["left", "right"])

        di_lines = f"Dev1/port0/line{LEFT_BUTTON_LINE}:{RIGHT_BUTTON_LINE}"
        with nidaqmx.Task() as task:
            # Ask the DAQ to detect on-flanks
            task.di_channels.add_di_chan(
                di_lines, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
            )
            task.timing.cfg_change_detection_timing(
                rising_edge_chan=di_lines,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=2,  # we read two samples to cover the up-flank
            )

            # Until we reach timeout, wait for the next up-flank
            clock = core.Clock()
            while timeout is None or timeout > 0:
                if timeout is not None:
                    timeout = max(timeout - clock.getTime(), 0)
                try:
                    button = task.read(
                        timeout=WAIT_INFINITELY if timeout is None else timeout
                    )
                    if button & (1 << LEFT_BUTTON_LINE):
                        return "left"
                    elif button & (1 << RIGHT_BUTTON_LINE):
                        return "right"
                except DaqReadError as e:
                    if e.error_code == -200284:  # timeout reached
                        return None
                    else:
                        raise e

        # We should probably have returned from the function in the while-loop above,
        # but in the off-chance we didn't, we have reached timeout.
        return None

    def wait_for_response(self, timeout=None, enable_channels="all"):
        """Wait until the participant responds using one of the multi-channel devices.

        The multi-channel devices are the tubular shaped devices with four light sensors
        on each device. Participants respond by lifting their finger.

        Parameters
        ----------
        timeout : float
            The number of seconds to wait for a response. When this time has elapsed,
            this function returns ``None`` indicating no response was received. You can
            specify ``timeout=None`` to wait indefinitely.
        enable_channels : list of int | "all"
            Which channels to enable. By default ("all"), all channels are enabled.
            However, if your experiment only uses a few of them, it's best to only
            listen to finger lifts on those and ignore the others. You can do this
            by setting this to a list of integer values (1-8) indicating which channels
            to listen for.

        Returns
        -------
        response : int | None
            A value 1-8 indicating which finger was lifted: 1-4 are on the right
            response device, 5-8 are on the left response device. Can also be
            None, indicating no response was given before the timeout was reached.

        See Also
        --------
        check_response_pad_held_correctly
        wait_until_response_pad_held_correctly

        """
        if enable_channels == "all":
            enable_channels = [1, 2, 3, 4, 5, 6, 7, 8]

        if self.fake:
            # Fake a random button press.
            core.wait(0.5 + 0.2 * random.random())
            return random.choice(enable_channels)

        di_lines = (
            f"Dev1/port0/line{RESPONSE_PAD_CHANNEL1_LINE}:{RESPONSE_PAD_CHANNEL8_LINE}"
        )
        di_rising_lines = (
            f"Dev1/port0/line{RESPONSE_PAD_CHANNEL3_LINE}:{RESPONSE_PAD_CHANNEL8_LINE}"
        )
        di_falling_lines = (
            f"Dev1/port0/line{RESPONSE_PAD_CHANNEL1_LINE}:{RESPONSE_PAD_CHANNEL2_LINE}"
        )
        with nidaqmx.Task() as task:
            # Ask the DAQ to detect on-flanks
            task.di_channels.add_di_chan(
                di_lines, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
            )
            task.timing.cfg_change_detection_timing(
                rising_edge_chan=di_rising_lines,
                falling_edge_chan=di_falling_lines,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=2,  # we read two samples to cover the up/down-flank
            )

            # Until we reach timeout, wait for the next up/down-flank
            clock = core.Clock()
            while timeout is None or timeout > 0:
                if timeout is not None:
                    timeout = max(timeout - clock.getTime(), 0)
                try:
                    button = task.read(
                        timeout=WAIT_INFINITELY if timeout is None else timeout
                    )
                    for channel in enable_channels:
                        mask = 1 << (RESPONSE_PAD_CHANNEL1_LINE + channel - 1)
                        if (channel == 1 or channel == 2) and (button & mask) == 0:
                            return channel
                        elif channel >= 3 and button & mask:
                            return channel
                except DaqReadError as e:
                    if e.error_code == -200284:  # timeout reached
                        return None
                    else:
                        raise e

        # We should probably have returned from the function in the while-loop above,
        # but in the off-chance we didn't, we have reached timeout.
        return None

    def check_response_pad_held_correctly(self, enable_channels="all"):
        """Check whether the participant is holding the response pad correctly.

        By correctly, we mean that the fingers that matter (see enable_channels)
        are properly covering the sensors, so that we may have a proper "finger lift"
        event later.

        Parameters
        ----------
        enable_channels : list of int | "all"
            Which channels to enable. By default ("all"), all channels are enabled.
            However, if your experiment only uses a few of them, it's best to only
            check the fingers on those and ignore the others. You can do this
            by setting this to a list of integer values (1-8) indicating which channels
            to listen for.

        Returns
        -------
        correct : bool
            Whether the participant is holding the response pad
            correctly (True) or not (False).

        See Also
        --------
        wait_until_response_pad_held_correctly
        wait_for_response

        """
        if enable_channels == "all":
            enable_channels = [1, 2, 3, 4, 5, 6, 7, 8]

        if self.fake:
            # Fake that sometimes (10%) the participant is not holding the
            # response pad correctly.
            return random.random() > 0.9

        di_lines = (
            f"Dev1/port0/line{RESPONSE_PAD_CHANNEL1_LINE}:{RESPONSE_PAD_CHANNEL8_LINE}"
        )
        with nidaqmx.Task() as task:
            # Ask the DAQ to detect on-flanks
            task.di_channels.add_di_chan(
                di_lines, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
            )
            task.timing.cfg_samp_clk_timing(
                2000.0,  # Hz
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=10,
            )
            data = task.read(READ_ALL_AVAILABLE)[-1]

            for channel in enable_channels:
                mask = 1 << (RESPONSE_PAD_CHANNEL1_LINE + channel - 1)
                if (channel == 1 or channel == 2) and (data & mask) == 0:
                    return False
                elif channel >= 3 and data & mask:
                    return False
        return True

    def wait_until_response_pad_held_correctly(
        self, timeout=None, enable_channels="all"
    ):
        """Wait until the participant is holding the response pad correctly.

        By correctly, we mean that the fingers that matter (see enable_channels)
        are properly covering the sensors, so that we may have a proper "finger lift"
        event later.

        Parameters
        ----------
        timeout : float
            The number of seconds to wait for the participant to adjust their grip.
            When this time has elapsed, this function returns ``False`` indicating
            the timeout was reached and the participant is still not holding the pad
            correctly. You can specify ``timeout=None`` to wait indefinitely.
        enable_channels : list of int | "all"
            Which channels to enable. By default ("all"), all channels are enabled.
            However, if your experiment only uses a few of them, it's best to only
            check the fingers on those and ignore the others. You can do this
            by setting this to a list of integer values (1-8) indicating which channels
            to listen for.

        Returns
        -------
        correct : bool
            Whether the participant is holding the response pad
            correctly (True) or that the timeout has been reached
            and the participant is still not holding it correctly (False).

        See Also
        --------
        check_response_pad_held_correctly
        wait_for_response

        """
        if self.check_response_pad_held_correctly(enable_channels=enable_channels):
            # Participant is already holding the pad correctly.
            return True

        if enable_channels == "all":
            enable_channels = [1, 2, 3, 4, 5, 6, 7, 8]

        if self.fake:
            # Fake the participant adjusting their grip.
            core.wait(0.5 + random.random())
            return True

        di_lines = (
            f"Dev1/port0/line{RESPONSE_PAD_CHANNEL1_LINE}:{RESPONSE_PAD_CHANNEL8_LINE}"
        )
        with nidaqmx.Task() as task:
            # Ask the DAQ to detect on-flanks
            task.di_channels.add_di_chan(
                di_lines, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
            )
            task.timing.cfg_change_detection_timing(
                rising_edge_chan=di_lines,
                falling_edge_chan=di_lines,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=2,  # we read two samples to cover the up/down-flank
            )

            # Until we reach timeout, wait for the next up/down-flank
            clock = core.Clock()
            correct = False
            while not correct and (timeout is None or timeout > 0):
                if timeout is not None:
                    timeout = max(timeout - clock.getTime(), 0)
                try:
                    data = task.read(
                        timeout=WAIT_INFINITELY if timeout is None else timeout
                    )
                    for channel in enable_channels:
                        mask = 1 << (RESPONSE_PAD_CHANNEL1_LINE + channel - 1)
                        if (channel == 1 or channel == 2) and (data & mask) == 0:
                            break  # not correct yet
                        elif channel >= 3 and data & mask:
                            break  # not correct yet
                    else:
                        # Grip seems correct now. Let's see if it's stable.
                        # There should not be any up/down flanks for 200ms.
                        try:
                            data = task.read(timeout=0.2)
                        except DaqReadError as e:
                            if e.error_code == -200284:  # timeout reached
                                correct = True
                except DaqReadError as e:
                    if e.error_code == -200284:  # timeout reached
                        return False
                    else:
                        raise e
        return correct


if __name__ == "__main__":
    meg = AaltoMEG()
    meg.send_trigger_code(1)
    print("Held correctly", meg.check_response_pad_held_correctly())
    print("Waiting for holding correctly...", flush=True)
    print("Success", meg.wait_until_response_pad_held_correctly())
    print("Held correctly", meg.check_response_pad_held_correctly())
    print("Waiting for response...")
    response = meg.wait_for_response(timeout=10)
    if response is None:
        print("Timeout.")
    else:
        print(f"Response: {response}")
