# Like API Documentation

## GET /likes?uid={uid}

**Example:** `http://localhost:5000/likes?uid=1234567890`

### Send like successfully
```json
{
  "result": {
    "User Info": {
      "Account UID": "1234567890",
      "Account Name": "PlayerName",
      "Account Region": "VN",
      "Account Level": "35",
      "Account Likes": 100
    },
    "Likes Info": {
      "Likes Added": 201,
      "Likes Before": 100,
      "Likes After": 301
    },
    "API": {
      "Success": true,
      "speeds": "2.3s"
    }
  }
}
```

### Account does not exist
```json
{"False": "Account does not exist"}
```

### Maximum like received (already liked today)
```json
{"Failed": "Maximum like received"}
```

### Reached max likes today
```json
{"False": "Account Id '1234567890' with name 'PlayerName' has reached max likes today, try again tomorrow !"}
```

### Not enough tokens
```json
{"message": "0"}
```

### Server error
```json
{"error": "..."}
```


