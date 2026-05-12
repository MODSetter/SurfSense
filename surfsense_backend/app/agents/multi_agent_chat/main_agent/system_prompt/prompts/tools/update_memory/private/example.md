<example>
<user_name>Alex</user_name>, <user_memory> is empty.
user: "I'm a space enthusiast, explain astrophage to me"
→ update_memory(updated_memory="## Interests & background\n- (2025-03-15) [fact] Alex is a space enthusiast\n")
(Casual durable fact; use first name, neutral heading.)
</example>

<example>
user: "Remember that I prefer concise answers over detailed explanations"
→ update_memory(updated_memory="## Interests & background\n- (2025-03-15) [fact] Alex is a space enthusiast\n\n## Response style\n- (2025-03-15) [pref] Alex prefers concise answers over detailed explanations\n")
(Durable preference; merge with existing memory.)
</example>

<example>
user: "I actually moved to Tokyo last month"
→ update_memory(updated_memory="...\n\n## Personal context\n- (2025-03-15) [fact] Alex lives in Tokyo (previously London)\n...")
(Updated fact; date reflects when recorded.)
</example>

<example>
user: "I'm a freelance photographer working on a nature documentary"
→ update_memory(updated_memory="...\n\n## Current focus\n- (2025-03-15) [fact] Alex is a freelance photographer\n- (2025-03-15) [fact] Alex is working on a nature documentary\n")
</example>

<example>
user: "Always respond in bullet points"
→ update_memory(updated_memory="...\n\n## Response style\n- (2025-03-15) [instr] Always respond to Alex in bullet points\n")
</example>
