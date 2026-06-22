import time, random, datetime
from teexez.ReQAPI import pb_encode, AES_CBC128

def getavatar():
    return random.choice([902046010, 902046009, 902000237, 902034023, 902040028, 902041012, 902000053, 902000029])

class GPackGEN:
    def __init__(self, logindata, jsdata):
        self.iv = bytes(jsdata["iv"])
        self.key = bytes(jsdata["key"])
        self.account_id = logindata.get(str(1))
        self.account_region = jsdata["LockRegion"]
        self.account_name = logindata.get(str(4), jsdata["UserNickName"])
        self.client_version = jsdata["ClientVersion"]

        sv_map = {s["2"].upper(): s["1"] for s in logindata["19"]}
        self.region_code = "%02X" % sv_map[self.account_region.upper()]

    def _build(self, fields):
        payload = AES_CBC128(pb_encode(dict(fields[1:])), self.key, self.iv).hex()
        length = hex(len(payload) // 2)[2:]
        pad = "0" * max(0, 8 - len(length))
        raw = "%02x%s%s%s%s" % (fields[0][1], self.region_code, pad, length, payload)
        return bytes.fromhex(raw)

    def _dig_tstamp(self):
        s = datetime.datetime.utcnow()
        nxt = s + datetime.timedelta(days=(7 - s.weekday()))
        nxt = nxt.replace(hour=6, minute=0, second=0, microsecond=0)
        return int(nxt.timestamp())

    def send_message(self, message, tp, chatid):
        fields = {}
        fields[0] = 18
        fields[1] = 1
        msg_body = {
            1: self.account_id,
            2: int(chatid),
            4: message,
            5: int(time.time()),
            9: {1: self.account_name, 2: getavatar(), 3: 901027033, 4: 228, 10: 11, 11: 101,
                13: {1: 2}, 14: {1: self.account_id, 2: 8, 3: bytes([15, 6, 21, 8, 10, 11, 19, 12, 17, 4, 14, 20, 7, 2, 1, 5, 16, 3, 13, 18])}},
            10: self.account_region.lower(),
            13: {2: 1, 3: 1},
            14: {1: {1: 1, 2: 1, 3: random.randint(1, 5), 4: 1, 5: self._dig_tstamp(), 6: self.account_region}}
        }
        if tp:
            msg_body[3] = int(tp)
            msg_body[7] = 2
        fields[2] = msg_body
        return self._build(list(fields.items()))

    def join_channel(self, cid, ccode, ctype):
        fields = {}
        fields[0] = 18
        fields[1] = 3
        entry = {3: self.account_region.lower()}
        if cid: entry[1] = int(cid)
        if ctype: entry[2] = int(ctype)
        if ccode: entry[4] = str(ccode)
        fields[2] = entry
        return self._build(list(fields.items()))

    def open_squad(self, tc):
        fields = {}
        fields[0] = 5
        fields[1] = 1
        fields[2] = {
            2: bytes([11]), 3: 1, 4: int(tc - 1), 9: 1,
            10: bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
            11: 1, 13: 1,
            14: {1: '', 2: 842, 6: 11, 8: self.client_version, 9: 6, 10: 1},
            19: 329
        }
        return self._build(list(fields.items()))

    def invite_squad(self, uid, tp):
        fields = {}
        fields[0] = 5
        fields[1] = 2
        fields[2] = {1: int(uid), 2: self.account_region, 4: int(tp)}
        return self._build(list(fields.items()))

    def leave_squad(self, uid=1):
        fields = {}
        fields[0] = 5
        fields[1] = 7
        fields[2] = {1: int(uid)}
        return self._build(list(fields.items()))

    def join_squad(self, tc):
        fields = {}
        fields[0] = 5
        fields[1] = 4
        fields[2] = {
            4: bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
            5: str(tc), 6: 6, 8: 1,
            9: {1: '', 2: 842, 6: 11, 8: self.client_version, 9: 6, 10: 1}
        }
        return self._build(list(fields.items()))

    def play_emote(self, eid, ids=None):
        if ids is None: ids = []
        fields = {}
        fields[0] = 5
        fields[1] = 21
        fields[2] = {1: self.account_id, 2: 0x362E3D41, 5: [{1: id, 3: eid} for id in ids]}
        return self._build(list(fields.items()))

    def play_animation(self, aid):
        fields = {}
        fields[0] = 5
        fields[1] = 88
        fields[2] = {}
        fields[2][1] = {}
        fields[2][1][1] = int(aid)
        return self._build(list(fields.items()))
