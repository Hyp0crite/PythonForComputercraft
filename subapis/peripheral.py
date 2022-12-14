from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple, Type, Any, Union

from .mixins import TermMixin, TermTarget
from .. import ser
from ..lua import LuaNum, LuaTable, lua_string
from ..sess import eval_lua, eval_lua_method_factory


class BasePeripheral:
    # NOTE: is not LuaExpr, you can't pass peripheral as parameter
    # TODO: to fix this we can supply separate lua expr, result of .wrap()

    def __init__(self, lua_method_expr, *prepend_params):
        self._lua_method_expr = lua_method_expr
        self._prepend_params = prepend_params

    def _method(self, name, *params):
        code = 'return ' + self._lua_method_expr + '(...)'
        return eval_lua(code, *self._prepend_params, ser.encode(name), *params)


class CCDrive(BasePeripheral):
    def isDiskPresent(self) -> bool:
        return self._method('isDiskPresent').take_bool()

    def getDiskLabel(self) -> Optional[str]:
        return self._method('getDiskLabel').take_option_string()

    def setDiskLabel(self, label: Optional[str]):
        return self._method('setDiskLabel', ser.nil_encode(label)).take_none()

    def hasData(self) -> bool:
        return self._method('hasData').take_bool()

    def getMountPath(self) -> Optional[str]:
        return self._method('getMountPath').take_option_string()

    def hasAudio(self) -> bool:
        return self._method('hasAudio').take_bool()

    def getAudioTitle(self) -> Optional[Union[bool, str]]:
        return self._method('getAudioTitle').take_option_string_bool()

    def playAudio(self):
        return self._method('playAudio').take_none()

    def stopAudio(self):
        return self._method('stopAudio').take_none()

    def ejectDisk(self):
        return self._method('ejectDisk').take_none()

    def getDiskID(self) -> Optional[int]:
        return self._method('getDiskID').take_option_int()


class CCMonitor(BasePeripheral, TermMixin):
    def getTextScale(self) -> int:
        return self._method('getTextScale').take_int()

    def setTextScale(self, scale: int):
        return self._method('setTextScale', scale).take_none()


class ComputerMixin:
    def turnOn(self):
        return self._method('turnOn').take_none()

    def shutdown(self):
        return self._method('shutdown').take_none()

    def reboot(self):
        return self._method('reboot').take_none()

    def getID(self) -> int:
        return self._method('getID').take_int()

    def getLabel(self) -> Optional[str]:
        return self._method('getLabel').take_option_string()

    def isOn(self) -> bool:
        return self._method('isOn').take_bool()


class CCComputer(BasePeripheral, ComputerMixin):
    pass


class CCTurtle(BasePeripheral, ComputerMixin):
    pass


@dataclass
class ModemMessage:
    reply_channel: int
    content: Any
    distance: LuaNum


class ModemMixin:
    def isOpen(self, channel: int) -> bool:
        return self._method('isOpen', channel).take_bool()

    def open(self, channel: int):
        return self._method('open', channel).take_none()

    def close(self, channel: int):
        return self._method('close', channel).take_none()

    def closeAll(self):
        return self._method('closeAll').take_none()

    def transmit(self, channel: int, replyChannel: int, message: Any):
        return self._method('transmit', channel, replyChannel, message).take_none()

    def isWireless(self) -> bool:
        return self._method('isWireless').take_bool()

    @property
    def _side(self):
        return self._prepend_params[0]

    def receive(self, channel: int):
        from .os import captureEvent

        if self.isOpen(channel):
            raise Exception('Channel is busy')

        self.open(channel)
        try:
            for evt in captureEvent('modem_message'):
                if evt[0] != self._side:
                    continue
                if evt[1] != channel:
                    continue
                yield ModemMessage(*evt[2:])
        finally:
            self.close(channel)


class CCWirelessModem(BasePeripheral, ModemMixin):
    pass


class CCWiredModem(BasePeripheral, ModemMixin):
    def getNameLocal(self) -> Optional[str]:
        return self._method('getNameLocal').take_option_string()

    def getNamesRemote(self) -> List[str]:
        return self._method('getNamesRemote').take_list_of_strings()

    def getTypeRemote(self, peripheralName: str) -> Optional[str]:
        return self._method('getTypeRemote', ser.encode(peripheralName)).take_option_string()

    def isPresentRemote(self, peripheralName: str) -> bool:
        return self._method('isPresentRemote', ser.encode(peripheralName)).take_bool()

    def wrapRemote(self, peripheralName: str) -> Optional[BasePeripheral]:
        # use instead getMethodsRemote and callRemote
        # NOTE: you can also use peripheral.wrap(peripheralName)

        ptype = self.getTypeRemote(peripheralName)
        if ptype is None:
            return None

        return TYPE_MAP[ptype](
            self._lua_method_expr, *self._prepend_params,
            b'callRemote', ser.encode(peripheralName),
        )

    # NOTE: for TermTarget use peripheral.get_term_target(peripheralName)


class CCPrinter(BasePeripheral):
    def newPage(self) -> bool:
        return self._method('newPage').take_bool()

    def endPage(self) -> bool:
        return self._method('endPage').take_bool()

    def write(self, text: str):
        return self._method('write', ser.dirty_encode(text)).take_none()

    def setCursorPos(self, x: int, y: int):
        return self._method('setCursorPos', x, y).take_none()

    def getCursorPos(self) -> Tuple[int, int]:
        rp = self._method('getCursorPos')
        return tuple(rp.take_int() for _ in range(2))

    def getPageSize(self) -> Tuple[int, int]:
        rp = self._method('getPageSize')
        return tuple(rp.take_int() for _ in range(2))

    def setPageTitle(self, title: str):
        return self._method('setPageTitle', ser.encode(title)).take_none()

    def getPaperLevel(self) -> int:
        return self._method('getPaperLevel').take_int()

    def getInkLevel(self) -> int:
        return self._method('getInkLevel').take_int()


class CCSpeaker(BasePeripheral):
    def playNote(self, instrument: str, volume: int = 1, pitch: int = 1) -> bool:
        # instrument:
        # https://minecraft.gamepedia.com/Note_Block#Instruments
        # bass
        # basedrum
        # bell
        # chime
        # flute
        # guitar
        # hat
        # snare
        # xylophone
        # iron_xylophone
        # pling
        # banjo
        # bit
        # didgeridoo
        # cow_bell

        # volume 0..3
        # pitch 0..24
        return self._method('playNote', ser.encode(instrument), volume, pitch).take_bool()

    def playSound(self, sound: str, volume: int = 1, pitch: int = 1) -> bool:
        # volume 0..3
        # pitch 0..2
        return self._method('playSound', ser.encode(sound), volume, pitch).take_bool()


class CCCommandBlock(BasePeripheral):
    def getCommand(self) -> str:
        return self._method('getCommand').take_string()

    def setCommand(self, command: str):
        return self._method('setCommand', ser.encode(command)).take_none()

    def runCommand(self):
        return self._method('runCommand').take_bool()


class CCWorkbench(BasePeripheral):
    def craft(self, quantity: int = 64):
        return self._method('craft', quantity).take_bool()


class CCInventory(BasePeripheral):
    def getItemDetail(self, slot: int) -> Optional[dict]:
        return self._method('getItemDetail', slot).take()

    def list(self) -> Dict[int, dict]:
        return self._method('list').take_dict()

    def pullItems(self, fromName: str, fromSlot: int, limit: int = None, toSlot: int = None) -> int:
        return self._method('pullItems', ser.encode(fromName), fromSlot, limit, toSlot).take_int()

    def pushItems(self, toName: str, fromSlot: int, limit: int = None, toSlot: int = None) -> int:
        return self._method('pushItems', ser.encode(toName), fromSlot, limit, toSlot).take_int()

    def size(self) -> int:
        return self._method('size').take_int()


class CCWebDisplay(BasePeripheral):
    def getURL(self) -> str:
        return self._method('getURL').take_string()

    def isLinked(self) -> bool:
        return self._method('isLinked').take_bool()

    def getOwner(self) -> Tuple[str, str]:
        rp = self._method('getOwner')
        return tuple(rp.take_string() for _ in range(2))

    def getSize(self) -> Tuple[int, int]:
        rp = self._method('getSize')
        return tuple(rp.take_int() for _ in range(2))

    def getRotation(self) -> int:
        return self._method('getRotation').take_int()

    def getScreenSide(self) -> str:
        return self._method('getScreenSide').take_string()

    def getResolution(self) -> Tuple[int, int]:
        rp = self._method('getResolution')
        return tuple(rp.take_int() for _ in range(2))

    def getScreenPos(self) -> Tuple[int, int, int]:
        rp = self._method('getScreenPos')
        return tuple(rp.take_int() for _ in range(3))

    def type(self, txt: str):
        return self._method('type', txt).take_bool()

    def click(self, x: int, y: int, act: str):
        return self._method('click', x, y, act).take_bool()

    def runJS(self, src: str):
        return self._method('runJS', src).take_bool()

    def setURL(self, url: str):
        return self._method('setURL', url).take_bool()

    def setRotation(self, ang: int):
        return self._method('setRotation', ang).take_bool()

    def setResolution(self, res_x: int, res_y: int):
        return self._method('setResolution', res_x, res_y).take_bool()


class CCNBTObserver(BasePeripheral):
    def readState(self) -> Dict[str, str]:
        return self._method('readState').take_dict()

    def hasState(self, arg: bytes):
        return self._method('hasState', arg).take_bool()

    def writeState(self, state):
        return self._method('writeState', state)

    def readNBT(self) -> str:
        return self._method('readNBT').take_string()

    def hasNBT(self, nbtKey: str):
        return self._method('hasNBT', nbtKey.encode('utf-8')).take_bool()

    def writeNBT(self, nbt: str):
        return self._method('writeNBT', nbt.encode('utf-8'))


class CC3dProjector(BasePeripheral):
    def write(self, model: list):
        return self._method('write', model)

    def clear(self):
        return self._method('clear')


class CCManipulator(BasePeripheral):

    def getBlockMeta(self, x: int, y: int, z: int):
        return self._method('getBlockMeta', x, y, z).take_dict()

    def sense(self):
        return self._method('sense').take_list()

    def getMetaByID(self, id: bytes):
        return self._method('getMetaByID', id).take_dict()

    def capture(self, pattern: str):
        return self._method('capture', pattern.encode('utf-8'))

    def clearCaptures(self):
        return self._method('clearCaptures')

    def say(self, message: str):
        return self._method('say', message.encode('utf-8'))

    def uncapture(self, pattern: str):
        return self._method('uncapture', pattern.encode('utf-8'))


TYPE_MAP = {}

method = eval_lua_method_factory('peripheral.')

__all__ = (
    'BasePeripheral',  # exposed for subclassing & registerType
    'CCInventory',  # exposed for registerType for 3rdparty mod inventory-like entities
    'isPresent',
    'getType',
    'getNames',
    'wrap',
    'registerType',
    'get_term_target',
)


def isPresent(side: str) -> bool:
    return method('isPresent', ser.encode(side)).take_bool()


def getType(side: str) -> Optional[str]:
    return method('getType', ser.encode(side)).take_option_string()


def getNames() -> List[str]:
    return method('getNames').take_list_of_strings()


# use instead getMethods and call
def wrap(side: str) -> Optional[BasePeripheral]:
    ptype = getType(side)
    if ptype is None:
        return None

    m = 'peripheral.call'

    side = ser.encode(side)
    if ptype == 'modem':
        if method('call', side, b'isWireless').take_bool():
            return CCWirelessModem(m, side)
        else:
            return CCWiredModem(m, side)
    else:
        return TYPE_MAP[ptype](m, side)


def registerType(ptype: str, pcls: Type[BasePeripheral]):
    TYPE_MAP[ptype] = pcls


def get_term_target(side: str) -> TermTarget:
    return TermTarget('peripheral.wrap({})'.format(
        lua_string(side),
    ))


registerType('drive', CCDrive)
registerType('monitor', CCMonitor)
registerType('computer', CCComputer)
registerType('turtle', CCTurtle)
registerType('printer', CCPrinter)
registerType('speaker', CCSpeaker)
registerType('command', CCCommandBlock)
registerType('workbench', CCWorkbench)
registerType('webdisplays', CCWebDisplay)
registerType('NBT_Observer', CCNBTObserver)
registerType('3d_projector', CC3dProjector)
registerType('manipulator', CCManipulator)

for k in [
    'chest',
    'furnace',
    'barrel',
    'hopper',
    'dropper',
    'dispenser',
    'blast_furnace',
    'smoker',
    'shulker_box',
    'brewing_stand',
]:
    registerType('minecraft:' + k, CCInventory)
