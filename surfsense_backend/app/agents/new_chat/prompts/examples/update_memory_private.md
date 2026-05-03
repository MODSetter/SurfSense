
- <user_name>Alex</user_name>, <user_memory> is empty. User: "I'm a space enthusiast, explain astrophage to me"
  - The user casually shared a durable fact. Use their first name in the entry, short neutral heading:
    update_memory(updated_memory="## Interests & background\n- (2025-03-15) [fact] Alex is a space enthusiast\n")
- User: "Remember that I prefer concise answers over detailed explanations"
  - Durable preference. Merge with existing memory, add a new heading:
    update_memory(updated_memory="## Interests & background\n- (2025-03-15) [fact] Alex is a space enthusiast\n\n## Response style\n- (2025-03-15) [pref] Alex prefers concise answers over detailed explanations\n")
- User: "I actually moved to Tokyo last month"
  - Updated fact, date prefix reflects when recorded:
    update_memory(updated_memory="## Interests & background\n...\n\n## Personal context\n- (2025-03-15) [fact] Alex lives in Tokyo (previously London)\n...")
- User: "I'm a freelance photographer working on a nature documentary"
  - Durable background info under a fitting heading:
    update_memory(updated_memory="...\n\n## Current focus\n- (2025-03-15) [fact] Alex is a freelance photographer\n- (2025-03-15) [fact] Alex is working on a nature documentary\n")
- User: "Always respond in bullet points"
  - Standing instruction:
    update_memory(updated_memory="...\n\n## Response style\n- (2025-03-15) [instr] Always respond to Alex in bullet points\n")
