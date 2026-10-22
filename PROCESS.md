# PROCESS.md — sound and interaction additions

## Tools and what for

For this extension, I used DeepSeek in a back-and-forth coding workflow to add sound and interaction to the existing temperature clock. The Python script generates a 24-second video with a sine tone whose pitch follows the interpolated hourly temperatures. The browser clock adds a date selector and lets visitors point to a clock sector to inspect its hour and temperature while hearing the corresponding tone. I used the browser's built-in Web Audio API, so the page does not need an audio file or microphone access. I also used Copilot SDK in VS Code to update these process notes.

## User test before explaining the experience

Before explaining how the experience works, I asked a classmate outside the project to try the browser clock. I did not explain the interaction first.

- **What they tried:** They selected a date, enabled sound, and moved the pointer over several clock sectors. They kept the pointer on a sector to read the displayed hour and temperature, then moved it away and tried again.
- **Where they hesitated:** They paused when they tried to read a sector's values while the tone kept sounding. Moving the pointer away made the tone fade, but then they could no longer see the specific hour and temperature. They seemed unsure how to inspect a reading without hearing the continuous tone.
- **Whether their reactions were reasonable:** Their reaction was reasonable. The interaction required hovering over a sector to see its exact values, but hovering also triggered a continuous tone that they found harsh and irritating. The task of reading the values and the task of avoiding the sound were in conflict.

## Decision from the observation

Based on this observation, I added a sound on/off switch so visitors can mute the tone while keeping the pointer on a sector to read its hour and temperature, then turn sound back on when they want to listen. This addresses the observed conflict between inspecting values and avoiding the continuous tone. It does not change the temperature-to-pitch mapping or the clock-sector readout.

## One thing I kept

I kept the direct mapping between temperature and pitch: each day's minimum and maximum map to 220 and 440 Hz, with intermediate temperatures mapped linearly. In the video, the hand and tone move continuously between hourly readings. In the browser, selecting a date and pointing to different hours updates the readout and tone; moving the pointer away fades the sound. This gives visitors a way to explore the same hourly pattern both visually and by listening.

## Interaction design decisions

The browser asks visitors to click **Enable sound** before playback, because browsers restrict audio autoplay. After that, the sound switch lets visitors mute or restore the tone while inspecting a sector, so they can read the exact hour and temperature without the continuous tone. The tone is a simple sine wave intended to make changes easier to notice, not to replace the displayed temperature values. The date selector and clock-sector interaction remain the main paths for exploring the data.