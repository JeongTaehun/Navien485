from typing import Dict, Any
from wallpad import Wallpad


class DeviceRegistry:
    """Registry for configuring and registering all devices."""
    
    def __init__(self, wallpad: Wallpad):
        self.wallpad = wallpad
        self._packet_mappings = {
            'percentage': {'00': '0', '01': '1', '02': '2', '03': '3'},
            'oscillation': {'03': 'oscillate_on', '00': 'oscillation_off', '01': 'oscillate_off'}
        }
    
    def _convert_percentage_to_hex(self, v: str) -> str:
        """
        환풍기 percentage를 RS485 hex로 변환
        직접 값 (1, 2, 3) 및 Home Assistant percentage (0, 33, 66, 100) 지원
        """
        # 먼저 직접 매핑 시도 (1, 2, 3)
        direct_mapping = {'0': '00', '1': '01', '2': '02', '3': '03'}
        if str(v) in direct_mapping:
            return direct_mapping[str(v)]
        
        # 그 다음 percentage 범위 처리 (33, 66, 100)
        try:
            num_val = float(v)
            
            if num_val == 0:
                return '00'  # OFF
            elif 1 <= num_val <= 35:  # 33% 범위
                return '01'  # 1단계 (약)
            elif 36 <= num_val <= 70:  # 66% 범위  
                return '02'  # 2단계 (중)
            elif 71 <= num_val <= 100:  # 100% 범위
                return '03'  # 3단계 (강)
            else:
                return '01'  # 기본값
                
        except (ValueError, TypeError):
            return '01'
    
    def register_all_devices(self) -> None:
        """Register all known devices with the wallpad."""
        self._register_heat_exchanger()
        self._register_gas_valve()
        self._register_lights()
        self._register_heating()
        self._register_elevator()
    
    def _register_heat_exchanger(self) -> None:
        """Register heat exchanger (전열교환기) device."""
        optional_info = {
            'optimistic': 'false',
            'speed_range_min': 1,
            'speed_range_max': 3
        }
        
        device = self.wallpad.add_device(
            device_name='전열교환기',
            device_id='32',
            device_subid='01',
            device_class='fan',
            optional_info=optional_info
        )
        
        # Status messages
        device.register_status(
            message_flag='01',
            attr_name='availability',
            topic_class='availability_topic',
            regex=r'()',
            process_func=lambda v: 'online'
        )
        
        device.register_status(
            message_flag='81',
            attr_name='power',
            topic_class='state_topic',
            regex=r'00(0[01])0[0-3]0[013]00',
            process_func=lambda v: 'ON' if v == '01' else 'OFF'
        )
        
        device.register_status(
            message_flag='81',
            attr_name='percentage',
            topic_class='percentage_state_topic',
            regex=r'000[01](0[0-3])0[013]00',
            process_func=lambda v: self._packet_mappings['percentage'][v]
        )
        
        # Command messages
        device.register_command(
            message_flag='41',
            attr_name='power',
            topic_class='command_topic',
            process_func=lambda v: '01' if v == 'ON' else '00'
        )
        
        device.register_command(
            message_flag='42',
            attr_name='percentage',
            topic_class='percentage_command_topic',
            process_func=self._convert_percentage_to_hex
        )
    
    def _register_gas_valve(self) -> None:
        """Register gas valve (가스) device."""
        optional_info = {'optimistic': 'false'}
        
        device = self.wallpad.add_device(
            device_name='가스',
            device_id='12',
            device_subid='01',
            device_class='switch',
            optional_info=optional_info
        )
        
        device.register_status(
            message_flag='01',
            attr_name='availability',
            topic_class='availability_topic',
            regex=r'()',
            process_func=lambda v: 'online'
        )
        
        device.register_status(
            message_flag='81',
            attr_name='power',
            topic_class='state_topic',
            regex=r'0(0[02])0',
            process_func=lambda v: 'ON' if v == '02' else 'OFF'
        )
        
        device.register_command(
            message_flag='41',
            attr_name='power',
            topic_class='command_topic',
            process_func=lambda v: '00' if v == 'ON' else '04'
        )
    
    def _register_lights(self) -> None:
        """Register lighting (조명) devices."""
        optional_info = {'optimistic': 'false'}
        
        device = self.wallpad.add_device(
            device_name='조명',
            device_id='0e',
            device_subid='1f',
            child_devices=["거실1", "거실2"],
            device_class='light',
            optional_info=optional_info
        )
        
        device.register_status(
            message_flag='81',
            attr_name='power',
            topic_class='state_topic',
            regex=r'0[01](0[01])(0[01])',
            process_func=lambda v: 'ON' if v == '01' else 'OFF'
        )
        
        device.register_command(
            message_flag='41',
            attr_name='power',
            topic_class='command_topic',
            controll_id=['11', '12'],
            process_func=lambda v: '01' if v == 'ON' else '00'
        )
    
    def _register_heating(self) -> None:
        """Register heating (난방) devices."""
        optional_info = {
            'modes': ['off', 'heat'],
            'temp_step': 1.0,
            'precision': 1.0,
            'min_temp': 10.0,
            'max_temp': 40.0,
            'send_if_off': 'false'
        }
        
        device = self.wallpad.add_device(
            device_name='난방',
            device_id='36',
            device_subid='1f',
            child_devices=["거실", "침실", "서재"],
            device_class='climate',
            optional_info=optional_info
        )
        
        # Status messages for different message flags
        for message_flag in ['81', '01']:
            device.register_status(
                message_flag=message_flag,
                attr_name='power',
                topic_class='mode_state_topic',
                regex=r'00([0-9a-fA-F]{2})[0-9a-fA-F]{18}',
                process_func=lambda v: 'heat' if v != 0 else 'off'
            )
            
            device.register_status(
                message_flag=message_flag,
                attr_name='away_mode',
                topic_class='away_mode_state_topic',
                regex=r'00[0-9a-fA-F]{2}([0-9a-fA-F]{2})[0-9a-fA-F]{16}',
                process_func=lambda v: 'ON' if v != 0 else 'OFF'
            )
            
            device.register_status(
                message_flag=message_flag,
                attr_name='currenttemp',
                topic_class='current_temperature_topic',
                regex=r'00[0-9a-fA-F]{10}([0-9a-fA-F]{2})[0-9a-fA-F]{2}([0-9a-fA-F]{2})[0-9a-fA-F]{2}([0-9a-fA-F]{2})',
                process_func=lambda v: int(v, 16)
            )
            
            device.register_status(
                message_flag=message_flag,
                attr_name='targettemp',
                topic_class='temperature_state_topic',
                regex=r'00[0-9a-fA-F]{8}([0-9a-fA-F]{2})[0-9a-fA-F]{2}([0-9a-fA-F]{2})[0-9a-fA-F]{2}([0-9a-fA-F]{2})[0-9a-fA-F]{2}',
                process_func=lambda v: int(v, 16)
            )
        
        # Command messages
        device.register_command(
            message_flag='43',
            attr_name='power',
            topic_class='mode_command_topic',
            controll_id=['11', '12', '13'],
            process_func=lambda v: '01' if v == 'heat' else '00'
        )
        
        device.register_command(
            message_flag='44',
            attr_name='targettemp',
            topic_class='temperature_command_topic',
            controll_id=['11', '12', '13'],
            process_func=lambda v: hex(int(float(v)))[2:]
        )
        
        device.register_command(
            message_flag='45',
            attr_name='away_mode',
            topic_class='away_mode_command_topic',
            controll_id=['11', '12', '13'],
            process_func=lambda v: '01' if v == 'ON' else '00'
        )
    
    def _register_elevator(self) -> None:
        """Register elevator (엘리베이터) device."""
        optional_info = {'modes': ['down']}  # 기존과 동일하게 유지
        
        device = self.wallpad.add_device(
            device_name='엘리베이터',
            device_id='33',
            device_subid='01',
            device_class='switch',  # 기존과 동일 (호환성)
            optional_info=optional_info
        )
        
        # 현재 층수 상태 (개선된 regex)
        device.register_status(
            message_flag='44',
            attr_name='floor',
            topic_class='current_floor_state_topic',  # 기존과 동일
            regex=r'01([0-9a-fA-F]{2})',  # 01 다음의 층수 바이트만 추출
            process_func=lambda v: int(v, 16)
        )
        
        # 스위치 상태 (기존 호환성)
        device.register_status(
            message_flag='44',
            attr_name='power',
            topic_class='state_topic',
            regex=r'()',
            process_func=lambda v: 'ON'
        )
        
        # 가용성 상태
        device.register_status(
            message_flag='01',
            attr_name='availability',
            topic_class='availability_topic',
            regex=r'()',
            process_func=lambda v: 'online'
        )
        
        # 엘리베이터 상태 - 이동 중
        device.register_status(
            message_flag='44',
            attr_name='elevator_status',
            topic_class='elevator_status_topic',
            regex=r'()',
            process_func=lambda v: 'moving'  # 층수 알림 = 이동 중
        )
        
        # 엘리베이터 상태 - 대기 (57, D7)
        device.register_status(
            message_flag='57',
            attr_name='power',
            topic_class='state_topic',
            regex=r'()',
            process_func=lambda v: 'OFF'
        )
        
        device.register_status(
            message_flag='d7',  # 소문자 d7로 수정
            attr_name='power',
            topic_class='state_topic',
            regex=r'()',
            process_func=lambda v: 'OFF'
        )
        
        # 엘리베이터 호출 명령 (기존과 동일)
        device.register_command(
            message_flag='81',
            attr_name='power',  # 기존과 동일
            topic_class='command_topic',  # 기존과 동일
            process_func=lambda v: '24' if v == 'ON' else '00'
        )