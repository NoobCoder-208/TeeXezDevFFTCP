# TeeXezDevTCP

FreeFire TCP Bot — chat + squad + actions over TCP socket.

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

## Critical Rules

### No Unauthorized Commits
- NEVER commit without explicit permission.
- Wait for user to say "commit" or "ok commit".
- Only stage files after user confirms.

### Surgical Changes
- Touch only what's asked. No adjacent "improvements".
- No AntiDisconnect, locks, shutdown cleanup, or auth sleep changes unless explicitly requested.
- No speculative optimizations.

### Squad Chat Implementation Reference
- `_process_0500_packet` — auto-accept invite + collect UIDs + join channels
- `join_channel(uid, code, None)` on chat socket for squad members
- Invite: code from parsed["5"]["8"]
- Player join: code from parsed["5"]["17"]

## Verify Before Reporting Done

- Syntax: `python3 -c "import py_compile; py_compile.compile('main.py', doraise=True)"`
- No log spam, no reconnect loops
- User tests and confirms before commit
