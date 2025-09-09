# Alison - AI Classroom IT Support Assistant

Alison is an AI-powered classroom IT support assistant that helps professors and proctors troubleshoot common technology issues in the classroom. She is designed to be a friendly and helpful first point of contact for any IT-related problems.

## Key Features

- **Conversational Troubleshooting:** Alison can understand natural language queries and provide step-by-step instructions to resolve common classroom technology issues.
- **Visual Guidance:** Alison can provide links to visual aids, such as diagrams and images, to help users better understand the troubleshooting steps.
- **Escalation Handling:** If an issue cannot be resolved through conversational troubleshooting, Alison will recommend contacting IT support and provide instructions on how to do so.
- **Role-Aware Responses:** Alison can provide different responses based on the user's role (e.g., professor or proctor).

## Enabling and Disabling Alison

Alison can be enabled or disabled through a configuration toggle in the NU Chatbot interface. When enabled, Alison will automatically handle any IT support-related queries. When disabled, all queries will be handled by the default NU Chatbot agent.

## Example Conversation Flows

### Example 1: Projector Not Working (Resolved)

**User (Professor):** "My projector is not working. I can't get it to turn on."

**Alison:** "I understand you're having an issue with: **the projector not turning on**. Here are some steps you can try:

1.  **Check Power Cable:** Ensure the projector's power cable is securely plugged into both the projector and a working power outlet.
2.  **Test Outlet:** Plug another device into the same outlet to confirm it's receiving power.
3.  **Use PowerButton:** Try turning on the projector using the physical power button on the unit itself, in case the remote's batteries are dead.

**Advice for you as a professor:**
Many classroom systems require you to select the source via a wall-mounted control panel. Please check for a control panel and select the correct input.

You can also refer to this visual guide: [Image: Diagram of projector ports and cable connections](alison_docs/images/projector_ports.png)"

### Example 2: Zoom Not Starting (Escalated)

**User (Proctor):** "Zoom is not starting on the classroom computer."

**Alison:** "I understand you're having an issue with: **Zoom not starting**. I'm sorry, but I was unable to find a solution for this issue in my knowledge base.

Please contact IT support for further assistance. You can contact IT support by visiting the help desk at [Location] or by calling [Phone Number]."
