OUTPOST PLAN — PHONE, LAPTOP FILTER, AND ESP32 DISPLAY
=====================================================
Part of: Phone MediaPipe landmarks → Laptop validation → ESP32 display
See also: phones.txt, display.txt


ROLE
----

The phone captures the subject and runs MediaPipe. It sends landmark frames to the
laptop over Wi-Fi. The laptop receives each frame, rejects invalid or unreliable
landmarks, and sends only the accepted landmark data to the ESP32 over 2.4 GHz.
The ESP32 receives the filtered data and drives the display.

Keep MediaPipe inference on the phone. The laptop is responsible only for packet
validation, landmark filtering, and forwarding. The ESP32 is responsible for
display timing and rendering.


DATAFLOW
--------

Phone ── landmarks over Wi-Fi ──► Laptop
                                      │
                                      ├─ reject malformed, stale, or low-quality landmarks
                                      └─ send accepted landmark data over 2.4 GHz
                                                       │
                                                       ▼
                                                     ESP32 ──► Display

Each phone frame is processed independently. The laptop does not combine multiple
camera views or create replacement landmarks. If a landmark is bad, it is omitted
from the outgoing frame.


LAN SETUP
---------

Use a dedicated 2.4 GHz local network with no internet dependency.

Primary — Laptop as Wi-Fi access point (recommended)
  Phone ──► 2.4 GHz Wi-Fi AP on laptop
  ESP32 ──► 2.4 GHz Wi-Fi AP on laptop

  Pros: one network for phone input and ESP32 output, simple addressing, no extra
        router, and native ESP32 compatibility
  Cons: AP mode can depend on the laptop Wi-Fi chipset and driver

Option B — Small dedicated 2.4 GHz router/AP (fallback)
  Phone ──► dedicated router/AP ──► Laptop
  ESP32 ──► dedicated router/AP

  Pros: stable Wi-Fi, better range, and easier IP management
  Cons: one additional device

Use Option B if the laptop cannot provide a reliable 2.4 GHz access point.


NETWORK SETTINGS
----------------

| Device          | IP            |
|-----------------|---------------|
| Laptop          | 192.168.50.1  |
| Phone           | 192.168.50.11 |
| ESP32           | 192.168.50.20 |

Subnet: 255.255.255.0
SSID: POSE-LAN
Security: WPA2
Band: 2.4 GHz
Channel: fixed to 1, 6, or 11 after checking local interference


IF MAKING THE LAPTOP THE ACCESS POINT
-------------------------------------

On Linux, use either NetworkManager or hostapd plus dnsmasq.

NetworkManager hotspot:
- Use the built-in hotspot feature if the adapter supports AP mode
- Set SSID to POSE-LAN and enable WPA2
- Select the 2.4 GHz band and a fixed channel
- Assign 192.168.50.1/24 to the AP interface

hostapd plus dnsmasq:
- Use hostapd for the Wi-Fi access point
- Use dnsmasq for DHCP
- Assign 192.168.50.1/24 to wlan0
- Set hw_mode=g for 2.4 GHz
- Use a fixed channel of 1, 6, or 11

Optional DHCP range:
  192.168.50.50 – 192.168.50.100

Before going live:
- Run `iw list` and confirm "AP" appears under supported interface modes
- Disable power saving on the Wi-Fi interface
- Keep the laptop plugged in
- Confirm that both the phone and ESP32 can reach 192.168.50.1


PHONE TO LAPTOP
---------------

The laptop listens for UDP landmark packets on port 9000.

UDP is appropriate because:
- Low latency matters more than retransmitting an old pose
- A dropped frame can be replaced by the next frame
- Sequence numbers make duplicate and out-of-order packets easy to reject

Firewall rule, if required:
  sudo ufw allow 9000/udp

Example phone packet:

{
  "seq": 1842,
  "t_capture_ms": 1784185200123,
  "landmarks": [
    {"i": 0, "x": 0.51, "y": 0.22, "z": -0.08, "v": 0.98},
    {"i": 1, "x": 0.49, "y": 0.25, "z": -0.06, "v": 0.91}
  ]
}

Required frame fields:
- seq: monotonically increasing frame sequence number
- t_capture_ms: phone capture timestamp in milliseconds
- landmarks: MediaPipe landmark records

Required landmark fields:
- i: landmark index
- x, y, z: finite coordinates
- v: visibility or confidence from 0.0 through 1.0


LAPTOP VALIDATION AND FILTERING
-------------------------------

Validate the packet before inspecting individual landmarks:
1. Reject invalid JSON or packets missing required fields
2. Reject duplicate or out-of-order sequence numbers
3. Reject frames older than MAX_FRAME_AGE_MS
4. Reject frames with an impossible landmark count or duplicate indices

Then validate every landmark:
1. Reject unknown indices
2. Reject NaN, infinity, non-numeric coordinates, or non-numeric visibility
3. Reject visibility below MIN_VISIBILITY
4. Reject coordinates outside configured safety bounds
5. Reject implausible jumps from the last accepted position

Do not fill rejected landmarks with zeroes. Omit them and include their indices in
the rejected list so the ESP32 can distinguish missing data from a real coordinate.
If fewer than MIN_GOOD_LANDMARKS survive, discard the entire frame.

Suggested starting values:

INGEST_PORT = 9000
ESP32_PORT = 9100
NUM_LANDMARKS = 33
MIN_VISIBILITY = 0.60
MAX_FRAME_AGE_MS = 150
MAX_JUMP_PER_FRAME = 0.25
MIN_GOOD_LANDMARKS = 12

Tune these values using captured data. The laptop should log rejection reasons and
counts so thresholds can be adjusted without guessing.


SUGGESTED LAPTOP MODULES
------------------------

  outpost/
    config.py      # addresses, ports, and validation thresholds
    models.py      # Landmark, LandmarkFrame, and FilteredFrame
    receiver.py    # UDP input from the phone
    validator.py   # frame and landmark quality checks
    sender.py      # compact UDP output to the ESP32
    main.py        # receive, filter, and forward loop

The forwarding path is:
1. Receive one phone packet
2. Parse and validate its frame metadata
3. Filter its landmarks
4. Drop the frame if too few landmarks remain
5. Encode the accepted landmarks
6. Send the filtered frame immediately to the ESP32

No fixed-rate processing loop is necessary. Processing each packet as it arrives
reduces latency and avoids forwarding duplicate state.


LAPTOP TO ESP32
---------------

Send filtered landmark frames over UDP to 192.168.50.20:9100 on the 2.4 GHz LAN.

Prototype output packet:

{
  "frame_id": 1842,
  "t_capture_ms": 1784185200123,
  "accepted": [
    {"i": 0, "x": 0.51, "y": 0.22, "z": -0.08, "v": 0.98},
    {"i": 1, "x": 0.49, "y": 0.25, "z": -0.06, "v": 0.91}
  ],
  "rejected": [2, 3]
}

Use JSON while prototyping because it is easy to inspect. Move to a compact binary
format after the pipeline works reliably. A binary packet should contain:
- Protocol version
- Frame ID
- Capture timestamp
- Accepted-landmark count
- Repeated index, x, y, z, and visibility values
- Checksum or CRC

Keep each UDP datagram below the network MTU to avoid IP fragmentation. Quantized
16-bit coordinates are preferable if JSON packets become too large.


ESP32 DISPLAY BEHAVIOR
----------------------

The ESP32 listens on UDP port 9100 and verifies each packet before display:
1. Reject unknown protocol versions or malformed payloads
2. Reject duplicate or older frame IDs
3. Verify packet length and checksum when using the binary format
4. Update only landmarks included in the accepted list
5. Mark rejected or missing landmarks unavailable
6. Blank or enter a safe idle state after a receive timeout

The ESP32 must not treat a missing landmark as coordinate zero. It may briefly hold
the last accepted value for visual stability, but it must expire held values after
a short timeout.


RELIABILITY PATTERNS
--------------------

- Use sequence numbers and ignore duplicates without blocking on gaps
- Drop old frames instead of queueing them
- Send a heartbeat every 250–500 ms when no landmark frame is available
- Add a laptop watchdog for phone input
- Add an ESP32 watchdog for laptop output
- Log phone packet rate, accepted count, rejected count, and forwarding rate
- Record rejection reasons separately: stale, low visibility, invalid coordinate,
  out of bounds, and implausible jump
- Keep the laptop-to-ESP32 packet small enough for one UDP datagram


SUGGESTED STACK
---------------

| Layer                | Choice                              |
|----------------------|-------------------------------------|
| Phone inference      | MediaPipe                           |
| Wi-Fi                | Dedicated 2.4 GHz WPA2 LAN          |
| Phone input          | UDP on laptop port 9000             |
| Laptop processing    | Python first; C++ if needed         |
| Landmark validation  | Range, confidence, age, and motion  |
| ESP32 output         | UDP on ESP32 port 9100              |
| Prototype encoding   | JSON                                |
| Production encoding  | Compact binary packet with CRC      |
| Display control      | ESP32 local rendering and timing    |


PRACTICAL SETUP SEQUENCE
------------------------

Step 1: Bring up POSE-LAN as a 2.4 GHz network
Step 2: Join the phone and ESP32; assign or reserve their IP addresses
Step 3: Verify phone-to-laptop and laptop-to-ESP32 UDP connectivity
Step 4: Send synthetic landmark packets from the phone
Step 5: Log all laptop validation decisions without forwarding
Step 6: Tune visibility, age, bounds, jump, and minimum-count thresholds
Step 7: Forward accepted landmark frames to the ESP32
Step 8: Display accepted landmarks and correctly hide rejected landmarks
Step 9: Test dropped packets, stale frames, bad coordinates, and disconnects
Step 10: Replace JSON with a compact binary format if packet size or parsing time
         affects display performance


TARGET LATENCY
--------------

Target phone capture to display update: 40–100 ms on a clean 2.4 GHz LAN.

Measure these stages independently:
- Phone inference and packet encoding
- Phone-to-laptop network transit
- Laptop validation and filtering
- Laptop-to-ESP32 network transit
- ESP32 packet parsing and display update

Favor the newest valid frame at every stage. A live display should drop delayed
data rather than build a backlog.
