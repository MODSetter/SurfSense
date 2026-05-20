
- <user_name>Alex</user_name>, <user_memory> is empty. User: "I'm a space enthusiast, explain astrophage to me"
  - The user casually shared a durable fact:
    update_memory(updated_memory="## Facts\n- 2025-03-15: Alex is a space enthusiast\n")
- User: "Remember that I prefer concise answers over detailed explanations"
  - Durable preference. Merge with existing memory:
    update_memory(updated_memory="## Facts\n- 2025-03-15: Alex is a space enthusiast\n\n## Preferences\n- 2025-03-15: Alex prefers concise answers over detailed explanations\n")
- User: "I actually moved to Tokyo last month"
  - Updated fact, date prefix reflects when recorded:
    update_memory(updated_memory="## Facts\n- 2025-03-15: Alex lives in Tokyo (previously London)\n...")
- User: "I'm a freelance photographer working on a nature documentary"
  - Durable background info under a fitting heading:
    update_memory(updated_memory="...\n\n## Current Focus\n- 2025-03-15: Alex is a freelance photographer\n- 2025-03-15: Alex is working on a nature documentary\n")
- User: "Always respond in bullet points"
  - Standing instruction:
    update_memory(updated_memory="...\n\n## Instructions\n- 2025-03-15: Always respond to Alex in bullet points\n")
