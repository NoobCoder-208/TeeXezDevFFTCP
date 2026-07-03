# TeeXezDevTCP - FreeFire TCP Bot

## Overview

FreeFire TCP Bot for chat + squad + actions over TCP socket.

## Project Structure

```
.
├── main.py                # Bot main: auth, chat handler, squad logic, 0500 packet handler
├── api.md                 # Like API documentation
└── teexez/
    ├── ReQAPI.py          # Garena auth, protobuf parser/encoder, AES-CBC128
    └── GPackGEN.py        # Game packet builder (chat, squad, emote, animation)
```

## Bot Flow

1. **Auth**: Read `bot.txt` → Garena guest token → MajorLogin → GetLoginData
2. **Connect**: TCP socket to Chat (39801) + Online (39699) servers
3. **Chat**: Receive 1200 packets → parse commands (`/help`, `/like`, `/5`, `/6`, `/js`, `/cut`, `/all`, `/share`)
4. **Squad**: Send/receive 0500 packets via Online socket → auto-accept invites, collect UIDs, join channels
5. **Reconnect**: Auto-reconnect on disconnect (chat 5s, online 3s), re-auth every 30s

## Key Dependencies

- `protobuf-decoder` — protobuf parsing
- `pycryptodome` — AES-CBC128 encryption
- `requests` — HTTP API calls

## Files

- **`main.py`**: Complete bot implementation with all chat and squad functionality
- **`api.md`**: Like API documentation
- **`teexez/ReQAPI.py`**: Garena authentication and packet encoding/decoding
- **`teexez/GPackGEN.py`**: Game packet builder for chat commands, squad actions, and animations

## Running

This is a daemon bot that requires:
- A `bot.txt` configuration file with UID/token
- Network connectivity to FreeFire servers
- TCP access to ports 39801 (chat) and 39699 (online)

The bot runs continuously with auto-reconnect and periodic re-authentication.

## Squad Chat Implementation Reference

- `_process_0500_packet` — auto-accept invite + collect UIDs + join channels
- `join_channel(uid, code, None)` on chat socket for squad members
- Invite: code from parsed["5"]["8"]
- Player join: code from parsed["5"]["17"]