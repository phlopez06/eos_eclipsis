# MIT License

# Copyright (c) 2023 [Philippe Lopez]

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import datetime
import time
import logging
import threading
from ctypes import *
from packages.EDSDK_Class import *
import traceback

edsdk = windll.edsdk

def foo():
    print(time.ctime())
    th = threading.Timer(10, foo)
    th.daemon = True
    th.start()
        
    # th.deamon
    # th.daemon
    # th.start()
        
class EOS_ECLIPSIS:
    def __init__(
            self,
            camera,
            contacts_date_time_dict, 
            knobs_dict,
            annular_eclipse=False,
            test_tse_rescheduler=False
            ) -> None:
        logging.info("*** EOS_ECLIPSIS Initialization ***")
        # Knobs
        self.knobs_dict = knobs_dict
        # Camera Object
        self.camera = camera
        # Date and Time of C1, C2, C3 and C4 
        self.contacts_date_time_dict = contacts_date_time_dict
        # Period used over Partial Phase to take C2/C3 photos
        self.before_c2_or_after_c3_time = knobs_dict['before_c2_or_after_c3_time']
        # Period used over Totality Phase to take C2/C3 photos
        self.after_c2_or_before_c3_time = knobs_dict['after_c2_or_before_c3_time']
        # Period Warning defined as the period of time the camera is busy after 1 shot
        self.busy_period_guarband = knobs_dict['busy_period_guarband']
        # Aperture Value for all Phases
        self.aperture = str(knobs_dict['aperture'])
        # ISO Speed Value for all Phases
        self.iso = str(knobs_dict['iso'])
        # Looping over all Phases
        self.loop_value = int(knobs_dict['loop_value'])
        # Period of time beween 2 shots during Partial Phase
        self.partial_period = knobs_dict['partial_period']
        # [Optional] Shutter Speed for Partial Phase - If not provided, will be calculated
        self.partial_shutterspeed = knobs_dict['partial_shutterspeed']
        # [Optional] Shutter Speed for "Diamonds Ring" Phase (At C2 and C3 Phase) - If not provided, will be calculated
        self.c2_c3_shutterspeed = knobs_dict['c2_c3_shutterspeed']
        # [Optional] Shutter Speed for Annularity Phase - If not provided, will be calculated
        self.annularity_shutterspeed = knobs_dict['annularity_shutterspeed']
        # Saving Mode. Default and currently only supported mode is 'Camera'
        self.saving_mode = "Camera"
        # Annular Eclipse ?
        self.annular_eclipse = annular_eclipse
        # Testing the Totality Rescheduler ?
        self.test_tse_rescheduler = test_tse_rescheduler
        # Print the execution Time while accessing the Camera
        try:
            self.print_execution_time = eval(knobs_dict['print_execution_time'])
        except:
            logging.critical(f'Could not evaluate the print_execution_time knob: {knobs_dict["print_execution_time"]}. A boolean True or False is expected')
            if self.camera is not None:
                exit()
        if not isinstance(self.print_execution_time, bool):
            logging.critical(f'The print_execution_time knob {self.print_execution_time} is not a boolean type. True or False boolean is expected')
            if self.camera is not None:
                exit()
        # Partiality
        # Shot Redundancy in Partial Phase Mode
        try:
            self.partial_shot_redundancy = int(knobs_dict['partial_shot_redundancy'])
        except:
            logging.critical(f'Could not convert the partial_shot_redundancy knob {knobs_dict["partial_shot_redundancy"]} to an integer type')
            self.partial_shot_redundancy = 1 if self.camera is None else exit()
        # Shot Duration in Partial Phase Mode
        try:
            self.partial_shot_duration = float(knobs_dict['partial_shot_duration'])
        except:
            logging.critical(f'Could not convert the partial_shot_duration knob {knobs_dict["partial_shot_duration"]} to a float type')
            self.partial_shot_duration = 1 if self.camera is None else exit()
        # Drive Modes
        if self.partial_shot_duration == 0:
            self.partial_drive_mode = 'Single shooting'
        else:
            self.partial_drive_mode = 'High speed continuous +'
        # Shutter Speed
        if self.partial_shutterspeed is None:
            self.partial_shutterspeed = self.calculate_shutterspeed(self.iso, self.aperture)
        try:
            self.partial_period = float(knobs_dict['partial_period'])
        except:
            logging.critical(f'Could not convert {knobs_dict["partial_period"]} partial_period parameter to a float type')
            if self.camera is not None:
                exit()

        # At C2 and C3 contacts
        # Drive Mode
        self.c2_c3_drive_mode = knobs_dict['c2_c3_drive_mode']
        if self.c2_c3_drive_mode not in DriveMode.Value:
            logging.critical(f'Drive Mode selected for Partial Phase is unknown: {self.c2_c3_drive_mode}')
            logging.info(f'Available Drive Mode: {list(DriveMode.Value.keys())}')
            self.c2_c3_drive_mode = next(iter(DriveMode.Value)) if self.camera is None else exit()
        # Time period overlap around C2 and C3 contacts
        try:
            self.after_c2_or_before_c3_time = float(knobs_dict['after_c2_or_before_c3_time'])
        except:
            logging.critical(f'Could not convert {knobs_dict["after_c2_or_before_c3_time"]} after_c2_or_before_c3_time parameter to a float type')
            if self.camera is not None:
                exit()
        try:
            self.before_c2_or_after_c3_time = float(knobs_dict['before_c2_or_after_c3_time'])
        except:
            logging.critical(f'Could not convert {knobs_dict["before_c2_or_after_c3_time"]} before_c2_or_after_c3_time parameter to a float type')
            if self.camera is not None:
                exit()
        if self.c2_c3_shutterspeed is None and self.before_c2_or_after_c3_time != 0 and self.after_c2_or_before_c3_time != 0:
            self.c2_c3_shutterspeed = f'1/{2*int(self.partial_shutterspeed[2:])}'
            logging.info(f'Calculated Shutter Speed for C2/C3 Phase: {self.c2_c3_shutterspeed}')

        # Annularity / Totality
        if annular_eclipse:
            # Shot Redundancy in Annularity Phase Mode
            try:
                self.annularity_shot_redundancy = int(knobs_dict['annularity_shot_redundancy'])
            except:
                logging.critical(f'Could not convert the annularity_shot_redundancy knob {knobs_dict["annularity_shot_redundancy"]} to an integer type')
                self.annularity_shot_redundancy = 1 if self.camera is None else exit()
            # Shot Duration in Annularity Phase Mode
            try:
                self.annularity_shot_duration = float(knobs_dict['annularity_shot_duration'])
            except:
                logging.critical(f'Could not convert the annularity_shot_duration knob {knobs_dict["annularity_shot_duration"]} to a float type')
                self.annularity_shot_duration = 1 if self.camera is None else exit()
            # Drive Modes
            if self.annularity_shot_duration == 0:
                self.annularity_drive_mode = 'Single shooting'
            else:
                self.annularity_drive_mode = 'High speed continuous +'
            # Shutter Speed
            if self.annularity_shutterspeed is None:
                self.annularity_shutterspeed = self.calculate_shutterspeed(self.iso, self.aperture)
            try:
                self.annularity_period = float(knobs_dict['annularity_period'])
            except:
                logging.critical(f'Could not convert {knobs_dict["annularity_period"]} annularity_period parameter to a float type')
                if self.camera is not None:
                    exit()

        else:
            # Dirve Mode
            self.totality_drive_mode = knobs_dict['totality_drive_mode']
            if self.totality_drive_mode not in DriveMode.Value:
                logging.critical(f'Drive Mode selected for Totality Phase is unknown: {self.totality_drive_mode}')
                logging.info(f'Available Drive Mode: {list(DriveMode.Value.keys())}')
                self.totality_drive_mode = next(iter(DriveMode.Value)) if self.camera is None else exit()
            # Max Frame per Second during Totality Phase
            try:
                self.totality_max_fps = float(knobs_dict['totality_max_fps'])
            except:
                logging.critical(f'Could not convert the totality_max_fps knob {knobs_dict["totality_max_fps"]} to a float type')
                self.totality_max_fps = 1 if self.camera is None else exit()
            # Totality Shutter Speed Sweep
            try:
                self.totality_sweep_shutterspeed = eval(knobs_dict['totality_sweep_shutterspeed'])
            except:
                logging.critical(f'Could not evaluate the Sweep Parameters. Must be defined as a list of string like ["start", "end", "incremental_step"]. Ex [`\'1/320\', \'1/5\', \'1/3\']')
                self.totality_sweep_shutterspeed = [] if self.camera is None else exit()
            self.totality_shutterspeed_sweep_list = self.get_sweep_list(self.totality_sweep_shutterspeed, 'Tv')
            # Totality Aperture Sweep
            try:
                self.totality_sweep_aperture = eval(knobs_dict['totality_sweep_aperture'])
            except:
                logging.critical(f'Could not evaluate the Sweep Parameters. Must be defined as a list of string like ["start", "end", "incremental_step"]. Ex [`\'8\', \'11\', \'1/3\']')
                self.totality_sweep_aperture = [] if self.camera is None else exit()
            self.totality_aperture_sweep_list = self.get_sweep_list(self.totality_sweep_aperture, 'Av')
            # Totality ISO Speed Sweep
            try:
                self.totality_sweep_iso = eval(knobs_dict['totality_sweep_iso'])
            except:
                logging.critical(f'Could not evaluate the Sweep Parameters. Must be defined as a list of string like ["start", "end", "incremental_step"]. Ex [`\'200\', \'400\', \'1/1\']')
                self.totality_sweep_iso = [] if self.camera is None else exit()
            self.totality_iso_sweep_list = self.get_sweep_list(self.totality_sweep_iso, 'ISO')


        # Miscellaneous 
        try:
            self.busy_period_guarband = float(knobs_dict['busy_period_guarband'])
        except:
            logging.critical(f'Could not convert {knobs_dict["busy_period_guarband"]} busy_period_guarband parameter to a float type')
            if self.camera is not None:
                exit()
        if self.camera is not None:
            self.camera.SetProperty(property=Property.SaveTo, parameter=Property.SaveTo_Camera, property_name='Save to Camera', start_time=self.timenow())
            logging.info(f"Photos Saving Mode set to {self.saving_mode}")

        self.c1_tstamp = self.convert_time_to_unix_timestamp(self.contacts_date_time_dict['c1_date'], self.contacts_date_time_dict['c1_time'])
        self.c2_tstamp = self.convert_time_to_unix_timestamp(self.contacts_date_time_dict['c2_date'], self.contacts_date_time_dict['c2_time'])
        self.c3_tstamp = self.convert_time_to_unix_timestamp(self.contacts_date_time_dict['c3_date'], self.contacts_date_time_dict['c3_time'])
        self.c4_tstamp = self.convert_time_to_unix_timestamp(self.contacts_date_time_dict['c4_date'], self.contacts_date_time_dict['c4_time'])

        if self.camera is not None:
            self.camera.SetProperty(property=Property.AEModeSelect, parameter=AEMode.Manual, property_name='AE Mode', start_time=self.timenow())
            logging.info(f"AE Mode set to Manual")
        
        self.auto_focus_mode = knobs_dict['auto_focus_mode']
        if self.auto_focus_mode != 'Off' and self.auto_focus_mode != 'On':
            logging.critical(f'Auto Focus Mode not supported: {self.auto_focus_mode}. "On" and "Off" only supported')
            if self.camera is not None:
                exit()

        logging.info("*** EOS_ECLIPSIS Initialization Completed ***")

    def utcnow(self):
        return datetime.datetime.timestamp(datetime.datetime.utcnow())
    
    def timenow(self):
        if self.print_execution_time:
            return time.time()
        else:
            return None

    def get_value(self, string, type, data):
        try:
            return eval(type)(data)
        except:
            logging.critical(f"Could not convert {string} {data} to an {type} type!")
            exit()

    def convert_time_to_unix_timestamp(self, current_date, current_time):
        if current_date.count('/') != 2:
            logging.critical(f"Unexpected date format. Must be YYYY/MM/DD!")
            if self.camera is not None:
                exit()
        year = self.get_value('year', 'int', current_date.split('/')[0])
        month = self.get_value('month', 'int', current_date.split('/')[1])
        day = self.get_value('day', 'int', current_date.split('/')[2])

        if current_time.count(':') != 2 and current_time.count(':') != 3:
            logging.critical(f"Unexpected time format. Must be HH:MM:SS or HH:MM:SS:ms!")
            if self.camera is not None:
                exit()
        hour = self.get_value('hour', 'int', current_time.split(':')[0])
        minute = self.get_value('minute', 'int', current_time.split(':')[1])
        second = self.get_value('second', 'int', current_time.split(':')[2])
        try:
            microsecond = 1000 * self.get_value('second', 'int', current_time.split(':')[3])
        except:
            microsecond = 0

        date_time = datetime.datetime(year, month, day, hour, minute, second, microsecond)
        unix_timestamp = datetime.datetime.timestamp(date_time)
        return unix_timestamp

    def get_metrics_tse(self, c2_tstamp=None, loop_value=None, totality_iso_sweep_list=None, totality_aperture_sweep_list=None, totality_shutterspeed_sweep_list=None):
        if c2_tstamp is None:
            c2_tstamp = self.c2_tstamp
        if loop_value is None:
            loop_value = self.loop_value
        if totality_iso_sweep_list is None:
            totality_iso_sweep_list = self.totality_iso_sweep_list
        if totality_aperture_sweep_list is None:
            totality_aperture_sweep_list = self.totality_aperture_sweep_list
        if totality_shutterspeed_sweep_list is None:
            totality_shutterspeed_sweep_list = self.totality_shutterspeed_sweep_list
        totality_nb_photos = 2 * loop_value * (len(totality_iso_sweep_list) + len(totality_aperture_sweep_list) + len(totality_shutterspeed_sweep_list))
        totality_exposure_duration = 0
        for exposure in totality_shutterspeed_sweep_list:
            totality_exposure_duration += eval(exposure.replace('h', ''))
        for _ in totality_iso_sweep_list + totality_aperture_sweep_list:
            totality_exposure_duration += eval(totality_shutterspeed_sweep_list[-1].replace("h", ""))
        totality_exposure_duration *= 2 * loop_value
        totality_margin_time = self.c3_tstamp - c2_tstamp - 2 * self.after_c2_or_before_c3_time - totality_exposure_duration - totality_nb_photos * self.busy_period_guarband
        totality_margin_time_per_photo = totality_margin_time / totality_nb_photos
        return totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo

    def get_sweep_list(self, sweep_factor_list, sweep_type) -> list:
        sweep_list = []
        if len(sweep_factor_list) == 3 and (sweep_factor_list[2] == "1/1" or sweep_factor_list[2] == "1/2" or sweep_factor_list[2] == "1/3"):
            for sweep_factor in sweep_factor_list[:-1]:
                if sweep_factor not in eval(sweep_type).Value:
                    logging.critical(f'{sweep_type} Sweep Value {sweep_factor} from the {sweep_factor_list} list does not exist from the available list')
                    logging.critical(f'Avalaible list: {list(eval(sweep_type).Value.keys())}')
                    if self.camera is not None:
                        exit()
        else:
            for sweep_factor in sweep_factor_list:
                if sweep_factor not in eval(sweep_type).Value:
                    logging.critical(f'{sweep_type} Sweep Value {sweep_factor} from the {sweep_factor_list} list does not exist from the available list')
                    logging.critical(f'Avalaible list: {list(eval(sweep_type).Value.keys())}')
                    if self.camera is not None:
                        exit()
            sweep_list = sweep_factor_list
        if sweep_factor_list and not sweep_list:
            sweep_start = sweep_factor_list[0]
            sweep_end = sweep_factor_list[1]
            sweep_step = sweep_factor_list[2]
            try:
                if float(sweep_start) > float(sweep_end):
                    sweep_temp = sweep_start
                    sweep_start = sweep_end
                    sweep_end = sweep_temp
            except:
                pass 
            if sweep_step not in ['1/3', '1/2', '1/1']:
                logging.critical(f'Incremental step {sweep_step} not supported for {sweep_type}. Supporting: 1/3 or 1/2 or 1/1')
                if self.camera is not None:
                    exit()
            elif sweep_type == 'ISO' and sweep_factor_list[2] == '1/2':
                logging.critical(f'Incremental step {sweep_step} not supported for {sweep_type}. Supporting: 1/3 or 1/1')
                if self.camera is not None:
                    exit()
            values_list = list(eval(sweep_type).Value.keys())
            if sweep_type == "Tv":
                values_list = list(reversed(values_list))
            if sweep_type == 'ISO':
                value_ref = "100"
            elif sweep_type == 'Tv':
                value_ref = "1/6000"
            elif sweep_type == 'Av':
                value_ref = "2.5h"
            idx_ref = values_list.index(value_ref)
            add_value_flag = False
            mod_val = None
            if sweep_type == "ISO":
                if sweep_step == "1/1":
                    mod_val = 3
                elif sweep_step == "1/3":
                    mod_val = 1
            elif sweep_type == "Tv" or sweep_type == "Av":
                if sweep_step == "1/1":
                    mod_val = 4
                elif sweep_step == "1/2":
                    mod_val = 2
                elif sweep_step == "1/3":
                    mod_val = 4
            if mod_val is not None:
                for idx, sweep_value in enumerate(values_list):
                    # Corner case for ISO start point defined below 100. No difference between 1/3 and 1/1 step => all values are added
                    if sweep_type == "ISO" and float(sweep_start) < 100 and sweep_value < 100:
                        sweep_list.append(sweep_value)
                        add_value_flag = True
                    if sweep_value == sweep_start:
                        add_value_flag = True
                    if add_value_flag:
                        if sweep_type == "Tv" or sweep_type == "Av":
                            if (idx_ref - idx) % mod_val == 0 and (sweep_step == "1/1" or sweep_step == "1/2"):
                                sweep_list.append(sweep_value)
                            elif (idx_ref - idx) % mod_val != 0 and sweep_step == "1/3":
                                sweep_list.append(sweep_value)
                        elif (idx_ref - idx) % mod_val == 0 and sweep_type == "ISO":
                            sweep_list.append(sweep_value)
                    if sweep_value == sweep_end:
                        add_value_flag = False
            if not sweep_list:
                sweep_list.append(sweep_start)
            logging.info(f'{sweep_type} Sweep List has {len(sweep_list)} points.')
            logging.info(f'{sweep_type} Sweep List: {str(sweep_list).replace("h", "")}')
        return sweep_list

    def calculate_shutterspeed(self, iso, aperture) -> str:
        av_list = list(Av.Value.keys())
        tv_list = list(reversed(list(Tv.Value.keys())))
        iso_list = list(ISO.Value.keys())
        iso_idx_ref = iso_list.index('100')
        av_idx_ref = av_list.index('11')
        tv_idx_ref = tv_list.index('1/250')
        if str(aperture) not in av_list:
            logging.error(f"Aperture value {aperture} is not supported")
            logging.info(f"Valid Aperture list: {av_list}")
            if self.camera is not None:
                exit()
        if iso not in iso_list:
            logging.error(f"ISO value {iso} is not supported")
            logging.info(f"Valid Aperture list: {iso_list}")
            if self.camera is not None:
                exit()

        # Av/Tv List index aligned for 100 ISO
        av_idx_tgt = av_list.index(aperture)
        iso_idx_tgt = iso_list.index(iso)
        shutterspeed_partial = tv_list[tv_idx_ref + (av_idx_tgt - av_idx_ref) - int(4/3*(iso_idx_tgt - iso_idx_ref))]
        logging.info(f"Calculated Shutter Speed for Partial Phase: {shutterspeed_partial}.")
        return shutterspeed_partial

    def check_input_data(self):
    # Check input data is all good before starting...
        if not self.c1_tstamp < self.c2_tstamp < self.c3_tstamp < self.c4_tstamp:
            logging.critical("Error in the chronology of the C1/C2/C3/C4 events")
            if self.c1_tstamp >= self.c2_tstamp:
                logging.critical(f'C1: {datetime.datetime.fromtimestamp(self.c1_tstamp)}. C2: {datetime.datetime.fromtimestamp(self.c2_tstamp)}')
            if self.c2_tstamp >= self.c3_tstamp:
                logging.critical(f'C2: {datetime.datetime.fromtimestamp(self.c2_tstamp)}. C3: {datetime.datetime.fromtimestamp(self.c3_tstamp)}')
            if self.c3_tstamp >= self.c4_tstamp:
                logging.critical(f'C3: {datetime.datetime.fromtimestamp(self.c3_tstamp)}. C4: {datetime.datetime.fromtimestamp(self.c4_tstamp)}')

        self.get_wait_time_until_event(self.c1_tstamp, 'C1')
        self.get_wait_time_until_event(self.c2_tstamp, 'C2')
        self.get_wait_time_until_event(self.c3_tstamp, 'C3')
        self.get_wait_time_until_event(self.c4_tstamp, 'C4')

        c1_c2_delta = datetime.timedelta(seconds=int(self.c2_tstamp-self.c1_tstamp))
        c2_c3_delta = datetime.timedelta(seconds=int(self.c3_tstamp-self.c2_tstamp))
        c2_c3_delta2 = datetime.timedelta(seconds=int(self.c3_tstamp-self.c2_tstamp-2*self.after_c2_or_before_c3_time))
        c3_c4_delta = datetime.timedelta(seconds=int(self.c4_tstamp-self.c3_tstamp))
        c1_c4_delta = datetime.timedelta(seconds=int(self.c4_tstamp-self.c1_tstamp))
        c2_c3_before_and_after_delta = datetime.timedelta(seconds=int(2*self.before_c2_or_after_c3_time+2*self.after_c2_or_before_c3_time))

        logging.info(f'Partial1 Phase Duration : {c1_c2_delta}')
        if self.annular_eclipse:
            logging.info(f'Annularity Phase Duration : {c2_c3_delta}')
        else:
            logging.info(f'Totality Phase Duration : {c2_c3_delta}')
        logging.info(f'Partial2 Phase Duration : {c3_c4_delta}')
        logging.info(f'Eclipse  Full  Duration : {c1_c4_delta}')

        nb_photos1 = int(round((self.c2_tstamp - self.c1_tstamp) / self.partial_period, 0))
        nb_photos2 = int(round((self.c4_tstamp - self.c3_tstamp) / self.partial_period, 0))
        logging.info(f'Number of photos while in Partial Phase 1       : {nb_photos1} photos.')
        logging.info(f'Number of photos while in Partial Phase 2       : {nb_photos2} photos.')

        if self.annular_eclipse:
            logging.info(f'Time window to take pictures during Annularity  : {c2_c3_delta2}.')
        else:
            logging.info(f'Time window to take pictures during Totality    : {c2_c3_delta2}.')
        logging.info(f'Time window to take pictures during C2 - C3     : {c2_c3_before_and_after_delta}.')
        rough_total_photos_c2_c3 = int(c2_c3_before_and_after_delta.total_seconds() / (self.busy_period_guarband + eval(self.c2_c3_shutterspeed)))
        logging.info(f'Rough total number of photos during C2 - C3     : {rough_total_photos_c2_c3} photos.')

        if not self.annular_eclipse:
            totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse()            
            rough_total_totality_photos = max(10 * int(totality_nb_photos * (totality_margin_time_per_photo * (self.totality_max_fps*0.9) / 10)), totality_nb_photos)
            logging.info(f'Period of Time allowed for taking pictures      : {round(self.c3_tstamp-self.c2_tstamp-2*self.after_c2_or_before_c3_time, 3)} seconds.')
            logging.info(f'Number of unique photos planned during Totality : {totality_nb_photos} photos.')
            logging.info(f'Rough total number of photos during Totality    : {rough_total_totality_photos} photos.')
            logging.info(f'Total Exposure Time during Totality             : {round(totality_exposure_duration, 3)} seconds.')
            logging.info(f'Estimated Camera Busy time after one shot       : {self.busy_period_guarband} seconds.')
            logging.info(f'Time margin left during Totality                : {round(totality_margin_time, 3)} seconds.')
            logging.info(f'Time margin left during Totality per photo      : {round(1e3*totality_margin_time_per_photo, 3)} milliseconds.')
            if self.busy_period_guarband != 0:
                logging.info(f'Relative Time margin vs Busy Time per photo     : {round(1e2*totality_margin_time_per_photo/self.busy_period_guarband, 2)} %.')
            logging.info(f'Number of Loop for the Totality Phase           : {self.loop_value}.')
            logging.info(f'Rough total number of photos during Eclipse     : {nb_photos1 + nb_photos2 + rough_total_photos_c2_c3 + rough_total_totality_photos} photos.')

            if totality_margin_time < 0:
                logging.critical('Will run into time issues during Totality. Change your input parameters!')
            elif totality_margin_time_per_photo < self.busy_period_guarband / 10:
                logging.critical('Most probably will run into time issues during Totality. Double-Check your input parameters!')
            elif totality_margin_time_per_photo < self.busy_period_guarband / 5:
                logging.error('May run into time issues during Totality. Check your input parameters or cross your fingers!')
            elif totality_margin_time_per_photo < self.busy_period_guarband / 2:
                logging.warning('Tight Schedule during the Totality!')
            else:
                logging.info('Schedule during the Totality looks OK!')

        self.get_value('Interval Time', 'int', self.busy_period_guarband)

        if self.iso not in ISO.Value:
            logging.critical('ISO Value is not defined in EDSDK Settings')
            logging.info(f'Available ISO: {list(ISO.Value.keys())}')
        elif self.camera is not None:
            self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())

        if self.aperture not in Av.Value:
            logging.critical('aperture Value is not defined in EDSDK Settings')
            logging.info(f'Available aperture: {list(Av.Value.keys())}')
        elif self.camera is not None:
            self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())

        if self.partial_shutterspeed not in Tv.Value:
            logging.critical(f'Shutter Speed Value is not defined in EDSDK Settings for partial phase: {self.partial_shutterspeed}')
            logging.info(f'Available Shutter Speed: {list(Tv.Value.keys())}')
        elif self.camera is not None:
            self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.partial_shutterspeed], property_name='Tv', start_time=self.timenow())

        if self.c2_c3_shutterspeed not in Tv.Value:
            logging.critical(f'Shutter Speed Value is not defined in EDSDK Settings for c2_c3 phase: {self.c2_c3_shutterspeed}')
            logging.info(f'Available Shutter Speed: {list(Tv.Value.keys())}')
        elif self.camera is not None: 
            self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.c2_c3_shutterspeed], property_name='Tv', start_time=self.timenow())

    def get_wait_time_until_event(self, current_timestamp, event=''):
        dt_object = datetime.datetime.fromtimestamp(current_timestamp)
        utcnow = self.utcnow()
        time_to_event = current_timestamp - utcnow
        time_to_last_event = self.c4_tstamp - utcnow
        converted_time_to_event = datetime.timedelta(seconds=int(time_to_event))

        if self.camera is None:
            if time_to_last_event < 0:
                if time_to_event < 0:
                    logging.critical(f"{event} Date/Time is a past event - Date/Time: {str(dt_object)[:-4]}")
                    logging.critical(f"Date/Time of Last Even is also a past event - Date/Time: {str(datetime.datetime.fromtimestamp(self.c4_tstamp))[:-4]}")
                else:
                    logging.info(f"{event} Date/Time will happen in {converted_time_to_event} !")
            elif time_to_event < 0:
                logging.info(f"{event} Date/Time is a past event - Date/Time: {str(dt_object)[:-4]}")
            else:
                logging.info(f"{event} Date/Time will happen in {converted_time_to_event} !")
        else:
            if time_to_last_event < 0:
                if time_to_event < 0:
                    logging.critical(f"{event} Date/Time is a past event - Date/Time: {str(dt_object)[:-4]}")
                    logging.critical(f"Date/Time of Last Even is also a past event - Date/Time: {str(datetime.datetime.fromtimestamp(self.c4_tstamp))[:-4]}")
                    # exit()
                elif time_to_event + max(self.before_c2_or_after_c3_time, self.after_c2_or_before_c3_time) > -1:
                    logging.info(f"{event} Date/Time is ~now~ - Date/Time: {str(dt_object)[:-4]}")
                else:
                    logging.warning(f"{event} Date/Time will happen in {converted_time_to_event} !")
            elif time_to_event > 43200:
                logging.critical(f"{event} Date/Time will happen in {converted_time_to_event} !")
                # exit()
            elif time_to_event > 14400:
                logging.warning(f"{event} Date/Time will happen in {converted_time_to_event} !")
            elif time_to_event > 0:
                logging.info(f"{event} Date/Time will happen in {converted_time_to_event} ...")
            elif time_to_event + max(self.before_c2_or_after_c3_time, self.after_c2_or_before_c3_time) + 2 > 0:
                logging.info(f"{event} Date/Time is a past event but in an expected guardband range - Date/Time: {str(dt_object)[:-4]}")
            else:
                logging.warning(f"{event} Date/Time is a past event - Date/Time: {str(dt_object)[:-4]}")
        return time_to_event

    def wait_period(self, time_to_event: int, event: str) -> None:
        now = datetime.datetime.timestamp(datetime.datetime.now())
        event_date_time = datetime.datetime.fromtimestamp(now + time_to_event)
        logging.info(f"Next Event {event} happening at {str(event_date_time)[:-4]} Local Time. Waiting for {round(time_to_event,3)}s.")
        if time_to_event > 5:
            for i in range(int(time_to_event), 0, -1):
                print("\t--> Countdown for Next Event " + str(event) + " at " + str(event_date_time)[:-4] + ": {:3d} seconds remaining <--".format(i), end="\r", flush=True)
                time.sleep(1)
            print("")
        elif time_to_event > 0:
            time.sleep(time_to_event)

    def reschedule_totality(self, c2_tstamp, totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo):
        if totality_margin_time < 0 or self.loop_value > 1 and totality_margin_time_per_photo < self.busy_period_guarband / 3:
            if self.loop_value > 1:
                if totality_margin_time < 0:
                    logging.warning('Total margin time is negative. Will first check if reducing the number of loop is mandatory')
                totality_sweep_iso = self.totality_sweep_iso[:-1] + ['1/1']
                totality_iso_sweep_list = self.get_sweep_list(totality_sweep_iso, 'ISO')
                totality_sweep_aperture = self.totality_sweep_aperture[:-1] + ['1/1']
                totality_aperture_sweep_list = self.get_sweep_list(totality_sweep_aperture, 'Av')
                totality_sweep_shutterspeed = self.totality_sweep_shutterspeed[:-1] + ['1/1']
                totality_shutterspeed_sweep_list = self.get_sweep_list(totality_sweep_shutterspeed, 'Tv')
                totality_nb_photos_temp, totality_exposure_duration_temp, totality_margin_time_temp, totality_margin_time_per_photo_temp = self.get_metrics_tse(
                    c2_tstamp=c2_tstamp,
                    totality_iso_sweep_list=totality_iso_sweep_list, 
                    totality_aperture_sweep_list=totality_aperture_sweep_list, 
                    totality_shutterspeed_sweep_list=totality_shutterspeed_sweep_list)
                while (self.loop_value > 0 and totality_margin_time_per_photo_temp < self.busy_period_guarband / 3):
                    self.loop_value -= 1
                    totality_nb_photos_temp, totality_exposure_duration_temp, totality_margin_time_temp, totality_margin_time_per_photo_temp = self.get_metrics_tse(
                        c2_tstamp=c2_tstamp,
                        totality_iso_sweep_list=totality_iso_sweep_list, 
                        totality_aperture_sweep_list=totality_aperture_sweep_list, 
                        totality_shutterspeed_sweep_list=totality_shutterspeed_sweep_list)
                if totality_margin_time_temp < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} with strong reduced set of sweep and no loop. Will try again...')
                    self.totality_sweep_iso = totality_sweep_iso
                    self.totality_iso_sweep_list = totality_iso_sweep_list
                    self.totality_sweep_aperture = totality_sweep_aperture
                    self.totality_aperture_sweep_list = totality_aperture_sweep_list
                    self.totality_sweep_shutterspeed = totality_sweep_shutterspeed
                    self.totality_shutterspeed_sweep_list = totality_shutterspeed_sweep_list
                    totality_nb_photos = totality_nb_photos_temp
                    totality_exposure_duration = totality_exposure_duration_temp
                    totality_margin_time = totality_margin_time_temp
                    totality_margin_time_per_photo = totality_margin_time_per_photo_temp
            if totality_margin_time < 0 and self.totality_sweep_shutterspeed[2] == '1/3':
                logging.warning('Total margin time is negative. Will switch the Shutter Speed step from 1/3 to 1/2')
                self.totality_sweep_shutterspeed = self.totality_sweep_shutterspeed[:-1] + ['1/2']
                self.totality_shutterspeed_sweep_list = self.get_sweep_list(self.totality_sweep_shutterspeed, 'Tv')
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            if totality_margin_time < 0 and self.totality_sweep_aperture and self.totality_sweep_aperture[2] == '1/3' and len(self.totality_aperture_sweep_list) > 1:
                logging.warning('Total margin time is negative. Will switch the Aperture step from 1/3 to 1/2')
                self.totality_sweep_aperture = self.totality_sweep_aperture[:-1] + ['1/2']
                self.totality_aperture_sweep_list = self.get_sweep_list(self.totality_sweep_aperture, 'Av')
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            if totality_margin_time < 0 and self.totality_sweep_iso and self.totality_sweep_iso[2] == '1/3' and len(self.totality_iso_sweep_list) > 1:
                logging.warning('Total margin time is negative. Will switch the ISO Speed step from 1/3 to 1/1')
                self.totality_sweep_iso = self.totality_sweep_iso[:-1] + ['1/1']
                self.totality_iso_sweep_list = self.get_sweep_list(self.totality_sweep_iso, 'ISO')
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            if totality_margin_time < 0 and self.totality_sweep_aperture and self.totality_sweep_aperture[2] != '1/1' and len(self.totality_aperture_sweep_list) > 1:
                logging.warning(f'Total margin time is negative. Will switch the Aperture step from {self.totality_sweep_aperture[2]} to 1/1')
                self.totality_sweep_aperture = self.totality_sweep_aperture[:-1] + ['1/1']
                self.totality_aperture_sweep_list = self.get_sweep_list(self.totality_sweep_aperture, 'Av')
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            if totality_margin_time < 0 and self.totality_sweep_shutterspeed[2] != '1/1':
                logging.warning(f'Total margin time is negative. Will switch the Shutter Speed step from {self.totality_sweep_shutterspeed[2]} to 1/1')
                self.totality_sweep_shutterspeed = self.totality_sweep_shutterspeed[:-1] + ['1/1']
                self.totality_shutterspeed_sweep_list = self.get_sweep_list(self.totality_sweep_shutterspeed, 'Tv')
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            if self.loop_value > 1 and totality_margin_time_per_photo < self.busy_period_guarband / 3:
                while (self.loop_value > 0 and totality_margin_time_per_photo < self.busy_period_guarband / 3):
                    self.loop_value -= 1
                    totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
                if totality_margin_time < 0:
                    logging.warning(f'Total margin time is still negative: {round(totality_margin_time, 3)} seconds. Will try again...')
            while(totality_margin_time < 0 and len(self.totality_shutterspeed_sweep_list) > 3):
                logging.warning('Total margin time is negative. Will cut the Shutter Speed Sweep List by 2')
                self.totality_shutterspeed_sweep_list = [speed for idx, speed in enumerate(self.totality_shutterspeed_sweep_list) if idx%2==0]
                totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp)
            if totality_margin_time < 0:
                logging.critical('Event after a drastic reduction on the sweep list, there will be not enough time to go throuh properly. Starting anyway...')
                totality_margin_time_per_photo = 0
            logging.warning('Sweep list(s) has/have reduced to fit this new plan into the remaining time window')
            logging.info(f'Tv Sweep: {self.totality_shutterspeed_sweep_list}')
            logging.info(f'Av Sweep: {self.totality_aperture_sweep_list}')
            logging.info(f'ISO Sweep: {self.totality_iso_sweep_list}')
        return totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo

    def partial_phase(self, partial_nb=0, force_exec=False) -> None:
        if partial_nb == 1:
            c1_tstamp = self.c1_tstamp
            c1_tstamp_adjusted = self.c1_tstamp
            c2_tstamp = self.c2_tstamp
            c2_tstamp_adjusted = self.c2_tstamp - self.before_c2_or_after_c3_time
        elif partial_nb == 2:
            c1_tstamp = self.c3_tstamp
            c1_tstamp_adjusted = self.c3_tstamp + self.before_c2_or_after_c3_time
            c2_tstamp = self.c4_tstamp
            c2_tstamp_adjusted = self.c4_tstamp + self.partial_period / 2
        elif force_exec:
            if self.c2_tstamp - self.c1_tstamp > self.c4_tstamp - self.c3_tstamp:
                c1_tstamp = c1_tstamp_adjusted = self.c1_tstamp
                c2_tstamp = c2_tstamp_adjusted = self.c2_tstamp
            else:
                c1_tstamp = c1_tstamp_adjusted = self.c3_tstamp
                c2_tstamp = c2_tstamp_adjusted = self.c4_tstamp
        c1_name = f'C{2*(partial_nb-1)+1}'
        c2_name = f'C{2*(partial_nb-1)+2}-Adjusted'

        if force_exec:
            logging.info(f"Camera Settings for Partial Phase {partial_nb} are ISO={self.iso}, Av={self.aperture}, Tv={self.partial_shutterspeed}s")
            self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.partial_shutterspeed], property_name='Tv', start_time=self.timenow())
            self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
            self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
            logging.info(f"Drive Mode for Partial Phase {partial_nb} set to {self.partial_drive_mode}")
            self.camera.SetProperty(property=Property.DriveMode, parameter=DriveMode.Value[self.partial_drive_mode], property_name='Drive Mode', start_time=self.timenow())
            logging.info(f"Start of the Partial Phase in forced execution...")
            nb_photos = int(round((c2_tstamp - c1_tstamp) / self.partial_period, 0))
            logging.info(f"Will take {nb_photos} photos every {self.partial_period}s...")
            for nb in range(nb_photos):
                if self.auto_focus_mode == 'On':
                    self.camera.SingleShootAF(start_time=self.timenow())
                else:
                    self.camera.BurstShootNonAF(duration=self.partial_shot_duration, start_time=self.timenow())
                logging.info(f"Photo n{nb+1} of Partial Phase {partial_nb} taken!")
                for i in range(self.partial_shot_redundancy):
                    if self.auto_focus_mode == 'On':
                        self.camera.SingleShootAF(start_time=self.timenow())
                    else:
                        self.camera.BurstShootNonAF(duration=self.partial_shot_duration, start_time=self.timenow())
                    logging.info(f"Redundancy n{i+1} of Photo n{nb+1} of Partial Phase {partial_nb} taken!")
                self.wait_period(self.partial_period, f"Photo n{nb+2} of Partial Phase {partial_nb}")
        else:
            c2_time_to_event = self.get_wait_time_until_event(c2_tstamp_adjusted, c2_name)
            if c2_time_to_event > 0:
                logging.info(f"Camera Settings for Partial Phase {partial_nb} are ISO={self.iso}, Av={self.aperture}, Tv={self.partial_shutterspeed}s")
                self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.partial_shutterspeed], property_name='Tv', start_time=self.timenow())
                self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                logging.info(f"Drive Mode for Partial Phase {partial_nb} set to {self.partial_drive_mode}")
                self.camera.SetProperty(property=Property.DriveMode, parameter=DriveMode.Value[self.partial_drive_mode], property_name='Drive Mode', start_time=self.timenow())

                utcnow = self.utcnow()
                c1_time_to_event = self.get_wait_time_until_event(c1_tstamp, c1_name)
                nb_photos = int(round((c2_tstamp - c1_tstamp) / self.partial_period, 0))
                adjusted_period = (c2_tstamp - c1_tstamp) / nb_photos
                if partial_nb == 2:
                    nb_photos += 1
                if c1_tstamp_adjusted + 2 < utcnow < c2_tstamp_adjusted:
                    adjusted_nb_photos = int(round((c2_tstamp - utcnow + self.partial_period) / adjusted_period, 0))
                    if partial_nb == 2:
                        adjusted_nb_photos += 1
                    logging.warning(f"You're running late for the Partial Phase {partial_nb} by {round(c1_tstamp_adjusted-utcnow, 3)} second(s)!")
                    if nb_photos > adjusted_nb_photos:
                        logging.warning(f"Will take {adjusted_nb_photos} photos instead of {nb_photos} as planned by original time window, every {round(adjusted_period, 3)}s...")
                    else:
                        logging.info(f"Anyway, Will take {nb_photos} photos as planned, every {round(adjusted_period, 3)}s... Only the first shot is belated...")
                else:
                    logging.info(f"Will take {nb_photos} photos as planned, every {round(adjusted_period, 3)}s...")
            
                if c1_time_to_event > 0:
                    logging.info("Start of the Pre-Partial Waiting Phase...")
                    if partial_nb == 2 and not self.annular_eclipse:
                        logging.info("")
                        logging.info(" ===>>> !! PLACE AGAIN THE SOLAR FILTER !! <<<===")
                        logging.info("")
                    self.wait_period(c1_time_to_event, c1_name)

                logging.info(f"Start of the Partial Phase...")
                if partial_nb == 2 and c1_time_to_event > -30 and not self.annular_eclipse:
                    logging.info("")
                    logging.info(" ===>>> !! PLACE AGAIN THE SOLAR FILTER !! <<<===")
                    logging.info("")
                next_time = c1_tstamp
                nb_photo_taken = 0
                while next_time < utcnow + 1:
                    next_time += adjusted_period
                time_to_next_event = next_time - utcnow
                while c2_time_to_event > time_to_next_event:
                    utcnow = self.utcnow()
                    while next_time < utcnow + 1:
                        next_time += adjusted_period
                    time_to_next_event = next_time - utcnow
                    if self.auto_focus_mode == 'On':
                        self.camera.SingleShootAF(start_time=self.timenow())
                    else:
                        self.camera.BurstShootNonAF(duration=self.partial_shot_duration, start_time=self.timenow())
                    nb_photo_taken += 1
                    logging.info(f"Photo n{nb_photo_taken} of Partial Phase {partial_nb} taken!")
                    for i in range(self.partial_shot_redundancy):
                        if self.auto_focus_mode == 'On':
                            self.camera.SingleShootAF(start_time=self.timenow())
                        else:
                            self.camera.BurstShootNonAF(duration=self.partial_shot_duration, start_time=self.timenow())
                        logging.info(f"Redundancy n{i+1} of Photo n{nb_photo_taken} of Partial Phase {partial_nb} taken!")
                    c2_time_to_event = self.get_wait_time_until_event(c2_tstamp_adjusted, c2_name)
                    time_to_next_event = next_time - self.utcnow()
                    if c2_time_to_event > time_to_next_event:
                        self.wait_period(time_to_next_event, f"Photo n{nb_photo_taken+1} of Partial Phase {partial_nb}")
                logging.info(f"End of Partial Phase {partial_nb}. {nb_photo_taken} photos taken!")
            else:
                logging.error(f"You're way too late for Partial Phase {partial_nb}. Phase skipped")

    def c2_c3_phases(self, contact=0, force_exec=False):
        c2_or_c3_time_to_event = c1_time_to_event = 1
        if not force_exec:
            if contact == 'C2':
                c2_or_c3_time_to_event = self.get_wait_time_until_event(self.c2_tstamp + self.after_c2_or_before_c3_time - self.busy_period_guarband, f'Contact {contact} End')
            elif contact == 'C3':
                c2_or_c3_time_to_event = self.get_wait_time_until_event(self.c3_tstamp + self.before_c2_or_after_c3_time, f'Contact {contact} End')
        if c2_or_c3_time_to_event > 0 or force_exec:
            logging.info(f"Camera Settings for C2/C3 Phase are ISO={self.iso}, Av={self.aperture}, Tv={self.c2_c3_shutterspeed}s")
            self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.c2_c3_shutterspeed], property_name='Tv', start_time=self.timenow())
            self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
            self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
            logging.info(f"Drive Mode for C2/C3 Phase set to {self.c2_c3_drive_mode}")
            self.camera.SetProperty(property=Property.DriveMode, parameter=DriveMode.Value[self.c2_c3_drive_mode], property_name='Drive Mode', start_time=self.timenow())

            # After Totality, setting properties may have taken time. Rechecking the time to events in any cases
            if not force_exec:
                if contact == 'C2':
                    c1_time_to_event = self.get_wait_time_until_event(self.c2_tstamp - self.before_c2_or_after_c3_time, f'Contact {contact} Start')
                    c2_or_c3_time_to_event = self.get_wait_time_until_event(self.c2_tstamp + self.after_c2_or_before_c3_time - self.busy_period_guarband, f'Contact {contact} End')
                elif contact == 'C3':
                    c1_time_to_event = self.get_wait_time_until_event(self.c3_tstamp - self.after_c2_or_before_c3_time, f'Contact {contact} Start')
                    c2_or_c3_time_to_event = self.get_wait_time_until_event(self.c3_tstamp + self.before_c2_or_after_c3_time, f'Contact {contact} End')

            if c1_time_to_event > 0 and not force_exec:
                logging.info(f"Start of the Contact {contact} Waiting Phase...")
                if contact == 'C2' and not self.annular_eclipse:
                    logging.info("")
                    logging.info(" ===>>> !! REMOVE THE SOLAR FILTER !! <<<===")
                    logging.info("")
                self.wait_period(c1_time_to_event, "Contact Start")

            if c2_or_c3_time_to_event > 0 or force_exec:
                if c1_time_to_event > 0 or force_exec:
                    duration = self.before_c2_or_after_c3_time + self.after_c2_or_before_c3_time
                else:
                    duration = c2_or_c3_time_to_event
                    if contact == 'C2' and not self.annular_eclipse:
                        logging.info("")
                        logging.info(" ===>>> !! REMOVE THE SOLAR FILTER !! <<<===")
                        logging.info("")
                if force_exec:
                    logging.info(f"Start of Contact for {duration} seconds in forced execution...")
                else:
                    logging.info(f"Start of Contact {contact} for {round(duration, 3)} seconds...")
                if 'continuous' in self.c2_c3_drive_mode:
                    self.camera.BurstShootNonAF(duration=duration, start_time=self.timenow())
                else:
                    start = self.utcnow()
                    while self.utcnow() < start + duration:
                        if self.auto_focus_mode == 'On':
                            self.camera.SingleShootAF(start_time=self.timenow())
                        else:
                            self.camera.BurstShootNonAF(start_time=self.timenow())
                logging.info(f"End of Contact...")
        else:
            logging.error(f"You're way too late for Contact {contact}. Phase skipped")

    def check_totality_phase(self, test_time_step=5):
        logging.info(f"Start of Totality Phase Check...")
        test_nb = 1
        c2_tstamp_ut = self.c2_tstamp
        while (self.c3_tstamp-c2_tstamp_ut-2*self.after_c2_or_before_c3_time > 0):
            logging.info('')
            logging.info(f' ===>> Test {test_nb}: <<===')

            # Reseting entry data for new test
            # Totality Shutter Speed Sweep
            self.totality_sweep_shutterspeed = eval(self.knobs_dict['totality_sweep_shutterspeed'])
            self.totality_shutterspeed_sweep_list = self.get_sweep_list(self.totality_sweep_shutterspeed, 'Tv')
            # Totality Aperture Sweep
            self.totality_sweep_aperture = eval(self.knobs_dict['totality_sweep_aperture'])
            self.totality_aperture_sweep_list = self.get_sweep_list(self.totality_sweep_aperture, 'Av')
            # Totality ISO Speed Sweep
            self.totality_sweep_iso = eval(self.knobs_dict['totality_sweep_iso'])
            self.totality_iso_sweep_list = self.get_sweep_list(self.totality_sweep_iso, 'ISO')

            totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=c2_tstamp_ut)
            totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.reschedule_totality(c2_tstamp_ut, totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo)
            rough_total_totality_photos = max(10 * int(totality_nb_photos * (totality_margin_time_per_photo * (self.totality_max_fps*0.9) / 10)), totality_nb_photos)

            logging.info(f'Period of Time allowed for taking pictures      : {round(self.c3_tstamp-c2_tstamp_ut-2*self.after_c2_or_before_c3_time, 3)} seconds.')
            logging.info(f'Number of unique photos planned during Totality : {totality_nb_photos} photos.')
            logging.info(f'Rough total number of photos during Totality    : {rough_total_totality_photos} photos.')
            logging.info(f'Total Exposure Time during Totality             : {round(totality_exposure_duration, 3)} seconds.')
            logging.info(f'Estimated Camera Busy time after one shot       : {self.busy_period_guarband} seconds.')
            logging.info(f'Time margin left during Totality                : {round(totality_margin_time, 3)} seconds.')
            logging.info(f'Time margin left during Totality per photo      : {round(1e3*totality_margin_time_per_photo, 3)} milliseconds.')
            if self.busy_period_guarband != 0:
                logging.info(f'Relative Time margin vs Busy Time per photo     : {round(1e2*totality_margin_time_per_photo/self.busy_period_guarband, 2)} %.')
            logging.info(f'Number of Loop for the Totality Phase           : {self.loop_value}.')

            test_nb += 1
            c2_tstamp_ut += test_time_step

    def totality_phase(self, force_exec=False, panic_mode=False):
        if panic_mode:
            if self.camera is not None:
                logging.info(f"Boarding Totality in panic mode...")
                self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                for shutterspeed in self.totality_shutterspeed_sweep_list:
                    self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[shutterspeed], property_name='Tv', start_time=self.timenow())
                    self.camera.BurstShootNonAF(duration=0, start_time=self.timenow())
                for aperture in self.totality_aperture_sweep_list:
                    self.camera.SetProperty(property=Property.Av, parameter=Av.Value[aperture], property_name='Av', start_time=self.timenow())
                    self.camera.BurstShootNonAF(duration=0, start_time=self.timenow())
                for iso in self.totality_iso_sweep_list + list(reversed(self.totality_iso_sweep_list)):
                    self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[iso], property_name='ISO', start_time=self.timenow())
                    self.camera.BurstShootNonAF(duration=0, start_time=self.timenow())
                if self.totality_iso_sweep_list:
                    self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                for aperture in reversed(self.totality_aperture_sweep_list):
                    self.camera.SetProperty(property=Property.Av, parameter=Av.Value[aperture], property_name='Av', start_time=self.timenow())
                    self.camera.BurstShootNonAF(duration=0, start_time=self.timenow())
                if self.totality_aperture_sweep_list:
                    self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                for shutterspeed in reversed(self.totality_shutterspeed_sweep_list):
                    self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[shutterspeed], property_name='Tv', start_time=self.timenow())
                    self.camera.BurstShootNonAF(duration=0, start_time=self.timenow())
                logging.info(f"End of the panic process...")
        else:
            if not force_exec:
                time_to_end = self.get_wait_time_until_event(self.c3_tstamp - self.after_c2_or_before_c3_time, 'Diamond Rings 2 Start')
            else:
                time_to_end = 1
            if time_to_end > 0 or force_exec:
                if force_exec:
                    logging.info(f"Start of Totality Phase in forced execution...")
                else:
                    logging.info(f"Start of Totality Phase...")
                if self.camera is not None:
                    logging.info(f"Camera Settings for Totality Phase are ISO={self.iso}, Av={self.aperture}")
                    self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                    self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                    logging.info(f"Drive Mode for Totality Phase set to {self.totality_drive_mode}")
                    self.camera.SetProperty(property=Property.DriveMode, parameter=DriveMode.Value[self.totality_drive_mode], property_name='Drive Mode', start_time=self.timenow())
                utcnow = self.utcnow()
                if self.c2_tstamp + self.after_c2_or_before_c3_time < utcnow - 2 and not force_exec:
                    logging.warning(f"You're Running late for Totality by {round(self.c2_tstamp + self.after_c2_or_before_c3_time - utcnow, 3)} second(s)!!")
                    # Re-checking if initial setting are still applicable with the shorten time period by looking at the total time margin
                    # and if the time margin is negative, will try to reduce the sweep list step by step until a margin become positive again if possible
                    totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse(c2_tstamp=self.utcnow())
                    self.reschedule_totality(self.utcnow, totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo)
                    rough_total_totality_photos = max(10 * int(totality_nb_photos * (totality_margin_time_per_photo * (self.totality_max_fps*0.9) / 10)), totality_nb_photos)
                    logging.info(f'New metrics for the Totality Phase:')
                    logging.info(f'Period of Time allowed for taking pictures      : {round(self.c3_tstamp-self.utcnow()-2*self.after_c2_or_before_c3_time, 3)} seconds.')
                    logging.info(f'Number of unique photos planned during Totality : {totality_nb_photos} photos.')
                    logging.info(f'Rough total number of photos during Totality    : {rough_total_totality_photos} photos.')
                    logging.info(f'Total Exposure Time during Totality             : {round(totality_exposure_duration, 3)} seconds.')
                    logging.info(f'Estimated Camera Busy time after one shot       : {self.busy_period_guarband} seconds.')
                    logging.info(f'Time margin left during Totality                : {round(totality_margin_time, 3)} seconds.')
                    logging.info(f'Time margin left during Totality per photo      : {round(1e3*totality_margin_time_per_photo, 3)} milliseconds.')
                    if self.busy_period_guarband != 0:
                        logging.info(f'Relative Time margin vs Busy Time per photo     : {round(1e2*totality_margin_time_per_photo/self.busy_period_guarband, 2)} %.')
                    logging.info(f'Number of Loop for the Totality Phase           : {self.loop_value}.')
                    next_event_time = self.utcnow()
                else:
                    totality_nb_photos, totality_exposure_duration, totality_margin_time, totality_margin_time_per_photo = self.get_metrics_tse()
                    if force_exec:
                        next_event_time = self.c2_tstamp + self.after_c2_or_before_c3_time
                    else:
                        next_event_time = max(self.utcnow(), self.c2_tstamp + self.after_c2_or_before_c3_time)
                    
                if self.camera is not None:
                    totality_weighted_exposure_duration = 0
                    for shutterspeed in self.totality_shutterspeed_sweep_list:
                        totality_weighted_exposure_duration += max(eval(shutterspeed.replace('h', '')), 1/self.totality_max_fps)
                    for _ in self.totality_iso_sweep_list + self.totality_aperture_sweep_list:
                        totality_weighted_exposure_duration += max(eval(self.totality_shutterspeed_sweep_list[-1].replace('h', '')), 1/self.totality_max_fps)
                    totality_weighted_exposure_duration *= 2 * self.loop_value
                    totality_weighted_margin_time = self.c3_tstamp - self.after_c2_or_before_c3_time - next_event_time - totality_weighted_exposure_duration

                    if force_exec:
                        next_event_time = self.utcnow()
                        
                    for loop_nb in range(self.loop_value):
                        if self.loop_value != 1:
                            logging.info("")
                            logging.info(f' ===>> Totality Phase Loop Number: {loop_nb + 1} <<===')
                        for shutterspeed in self.totality_shutterspeed_sweep_list:
                            shutterspeed_str = shutterspeed.replace('h', '')
                            shutterspeed_eval = eval(shutterspeed_str)
                            duration = (max(shutterspeed_eval, 1/self.totality_max_fps) / totality_weighted_exposure_duration) * totality_weighted_margin_time + max(shutterspeed_eval, 1/self.totality_max_fps)
                            next_event_time += duration
                            utcnow = self.utcnow()
                            if next_event_time > utcnow - 1 or force_exec:
                                self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[shutterspeed], property_name='Tv', start_time=self.timenow())
                                logging.info(f'Shoot at {shutterspeed_str} Shutter Speed and {self.aperture} Aperture and {self.iso} ISO for {round(duration, 3)} s.')
                                self.camera.BurstShootNonAF(duration=duration, next_event_time=next_event_time-self.busy_period_guarband/2, start_time=self.timenow())
                            else:
                                logging.error(f'Skipping pictures at Shutter Speed {shutterspeed_str} as we are running late by {round(next_event_time-utcnow, 3)} seconds on the schedule')
                        for aperture in self.totality_aperture_sweep_list:
                            next_event_time += duration
                            utcnow = self.utcnow()
                            if next_event_time > utcnow - 1 or force_exec:
                                self.camera.SetProperty(property=Property.Av, parameter=Av.Value[aperture], property_name='Av', start_time=self.timenow())
                                logging.info(f'Shoot at {shutterspeed_str} Shutter Speed and {aperture} Aperture and {self.iso} ISO for {round(duration, 3)} s.')
                                self.camera.BurstShootNonAF(duration=duration, next_event_time=next_event_time-self.busy_period_guarband/2, start_time=self.timenow())
                            else:
                                logging.error(f'Skipping pictures at Shutter Speed {shutterspeed_str} as we are running late by {round(next_event_time-utcnow, 3)} seconds on the schedule')
                        for iso in self.totality_iso_sweep_list + list(reversed(self.totality_iso_sweep_list)):
                            next_event_time += duration
                            utcnow = self.utcnow()
                            if next_event_time > utcnow -1 or force_exec:
                                self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[iso], property_name='ISO', start_time=self.timenow())
                                logging.info(f'Shoot at {shutterspeed_str} Shutter Speed and {aperture} Aperture and {iso} ISO for {round(duration, 3)} s.')
                                self.camera.BurstShootNonAF(duration=duration, next_event_time=next_event_time-self.busy_period_guarband/2, start_time=self.timenow())
                            else:
                                logging.error(f'Skipping pictures at ISO Speed {iso} as we are running late on the schedule')
                        if self.totality_iso_sweep_list:
                            self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                        for aperture in reversed(self.totality_aperture_sweep_list):
                            next_event_time += duration
                            utcnow = self.utcnow()
                            if next_event_time > utcnow - 1 or force_exec:
                                self.camera.SetProperty(property=Property.Av, parameter=Av.Value[aperture], property_name='Av', start_time=self.timenow())
                                logging.info(f'Shoot at {shutterspeed_str} Shutter Speed and {aperture} Aperture and {self.iso} ISO for {round(duration, 3)} s.')
                                self.camera.BurstShootNonAF(duration=duration, next_event_time=next_event_time-self.busy_period_guarband/2, start_time=self.timenow())
                            else:
                                logging.error(f'Skipping pictures at Shutter Speed {shutterspeed_str} as we are running late by {round(next_event_time-utcnow, 3)} seconds on the schedule')
                        if self.totality_aperture_sweep_list:
                            self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                        for shutterspeed in reversed(self.totality_shutterspeed_sweep_list):
                            shutterspeed_str = shutterspeed.replace('h', '')
                            shutterspeed_eval = eval(shutterspeed_str)
                            duration = (max(shutterspeed_eval, 1/self.totality_max_fps) / totality_weighted_exposure_duration) * totality_weighted_margin_time + max(shutterspeed_eval, 1/self.totality_max_fps)
                            next_event_time += duration
                            utcnow = self.utcnow()
                            if next_event_time > utcnow - 1 or force_exec:
                                self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[shutterspeed], property_name='Tv', start_time=self.timenow())
                                logging.info(f'Shoot at {shutterspeed_str} Shutter Speed and {self.aperture} Aperture and {self.iso} ISO for {round(duration, 3)} s.')
                                self.camera.BurstShootNonAF(duration=duration, next_event_time=next_event_time-self.busy_period_guarband/2, start_time=self.timenow())
                            else:
                                logging.error(f'Skipping pictures at Shutter Speed {shutterspeed_str} as we are running late by {round(next_event_time-utcnow, 3)} seconds on the schedule')
                logging.info(f"End of Totality Phase...")

            else:
                logging.error(f"You're way too late for Totality. Phase skipped")

    def annularity_phase(self, force_exec=False):
        if not force_exec:
            time_to_end = self.get_wait_time_until_event(self.c3_tstamp - self.after_c2_or_before_c3_time, 'Contact C3 Start')
        else:
            time_to_end = 1
        if time_to_end > 0 or force_exec:
            if force_exec:
                logging.info(f"Start of Annularity Phase in forced execution...")
            else:
                logging.info(f"Start of Annularity Phase...")
            if self.camera is not None:
                logging.info(f"Camera Settings for Annularity Phase are ISO={self.iso}, Av={self.aperture}, Tv={self.annularity_shutterspeed}s")
                self.camera.SetProperty(property=Property.Tv, parameter=Tv.Value[self.annularity_shutterspeed], property_name='Tv', start_time=self.timenow())
                self.camera.SetProperty(property=Property.Av, parameter=Av.Value[self.aperture], property_name='Av', start_time=self.timenow())
                self.camera.SetProperty(property=Property.ISOSpeed, parameter=ISO.Value[self.iso], property_name='ISO', start_time=self.timenow())
                logging.info(f"Drive Mode for Annularity Phase set to {self.annularity_drive_mode}")
                self.camera.SetProperty(property=Property.DriveMode, parameter=DriveMode.Value[self.annularity_drive_mode], property_name='Drive Mode', start_time=self.timenow())
        if force_exec:
            nb_photos = int(round((self.c3_tstamp - self.c2_tstamp) / self.annularity_period, 0))
            logging.info(f"Will take {nb_photos} photos every {self.annularity_period}s...")
            for nb in range(nb_photos):
                if self.auto_focus_mode == 'On':
                    self.camera.SingleShootAF(start_time=self.timenow())
                else:
                    self.camera.BurstShootNonAF(duration=self.annularity_shot_duration, start_time=self.timenow())
                logging.info(f"Photo n{nb+1} of Annularity Phase taken!")
                for i in range(self.annularity_shot_redundancy):
                    if self.auto_focus_mode == 'On':
                        self.camera.SingleShootAF(start_time=self.timenow())
                    else:
                        self.camera.BurstShootNonAF(duration=self.annularity_shot_duration, start_time=self.timenow())
                    logging.info(f"Redundancy n{i+1} of Photo n{nb+1} of Annularity Phase taken!")
                self.wait_period(self.annularity_period, f"Photo n{nb+2} of Annularity Phase")
        elif time_to_end > 0:
            c3_time_to_event = self.get_wait_time_until_event(self.c3_tstamp - self.after_c2_or_before_c3_time, 'Contact C3 Start')
            if c3_time_to_event > 0:
                utcnow = self.utcnow()
                nb_photos = int(round((self.c3_tstamp - self.c2_tstamp - 2 * self.after_c2_or_before_c3_time) / self.annularity_period, 0))
                adjusted_period = (self.c3_tstamp - self.c2_tstamp - 2 * self.after_c2_or_before_c3_time) / nb_photos
                if self.c2_tstamp + self.after_c2_or_before_c3_time + 2 < utcnow < self.c3_tstamp:
                    adjusted_nb_photos = int(round((self.c3_tstamp - self.after_c2_or_before_c3_time - utcnow + self.annularity_period) / adjusted_period, 0))
                    logging.warning(f"You're running late for the Annularity Phase by {round(self.c2_tstamp + self.after_c2_or_before_c3_time - utcnow, 3)} second(s)!")
                    if nb_photos > adjusted_nb_photos:
                        logging.warning(f"Will take {adjusted_nb_photos} photos instead of {nb_photos} as planned by original time window, every {round(adjusted_period, 3)}s...")
                    else:
                        logging.info(f"Anyway, Will take {nb_photos} photos as planned, every {round(adjusted_period, 3)}s... Only the first shot is belated...")
                else:
                    logging.info(f"Will take {nb_photos} photos as planned, every {round(adjusted_period, 3)}s...")
            
                next_time = self.c2_tstamp + self.after_c2_or_before_c3_time
                nb_photo_taken = 0
                utcnow = self.utcnow()
                while next_time < utcnow:
                    next_time += adjusted_period
                time_to_next_event = next_time - utcnow
                while c3_time_to_event > time_to_next_event:
                    utcnow = self.utcnow()
                    while next_time < utcnow:
                        next_time += adjusted_period
                    time_to_next_event = next_time - utcnow
                    if self.auto_focus_mode == 'On':
                        self.camera.SingleShootAF(start_time=self.timenow())
                    else:
                        self.camera.BurstShootNonAF(duration=self.annularity_shot_duration, start_time=self.timenow())
                    nb_photo_taken += 1
                    logging.info(f"Photo n{nb_photo_taken} of Annularity Phase taken!")
                    for i in range(self.annularity_shot_redundancy):
                        if self.auto_focus_mode == 'On':
                            self.camera.SingleShootAF(start_time=self.timenow())
                        else:
                            self.camera.BurstShootNonAF(duration=self.annularity_shot_duration, start_time=self.timenow())
                        logging.info(f"Redundancy n{i+1} of Photo n{nb_photo_taken} of Annularity Phase taken!")
                    c3_time_to_event = self.get_wait_time_until_event(self.c3_tstamp - self.after_c2_or_before_c3_time, 'Contact C3 Start')
                    time_to_next_event = next_time - self.utcnow()
                    if c3_time_to_event > time_to_next_event:
                        self.wait_period(time_to_next_event, f"Photo n{nb_photo_taken+1} of Annularity Phase")
                logging.info(f"End of Annularity Phase. {nb_photo_taken} photos taken!")
            else:
                logging.error(f"You're way too late for Annularity. Phase skipped")
            logging.info(f"End of Annularity Phase...")
        else:
            logging.error(f"You're way too late for Annularity. Phase skipped")

    def run_tse(self):
        self.check_input_data()
        if self.camera is not None:
            logging.info("*** START OF THE PROGRAM ***")
            self.partial_phase(1)
            self.c2_c3_phases('C2')
            self.totality_phase()
            self.c2_c3_phases('C3')
            self.partial_phase(2)
            logging.info("*** END OF THE PROGRAM ***")
        elif self.test_tse_rescheduler:
            logging.info("*** TESTING THE TOTALITY RESCHEDULER ***")
            self.check_totality_phase()
            
    def run_ase(self):
        self.check_input_data()
        if self.camera is not None:
            logging.info("*** START OF THE PROGRAM ***")
            self.partial_phase(1)
            self.c2_c3_phases('C2')
            self.annularity_phase()
            self.c2_c3_phases('C3')
            self.partial_phase(2)
            logging.info("*** END OF THE PROGRAM ***")

