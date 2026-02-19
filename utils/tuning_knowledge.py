"""Pro Late Model Oval Track Tuning Knowledge Base.

This module contains expert racing knowledge used to enhance AI
recommendations in the Trackside Tuning page. The knowledge is
injected into the AI system prompt so Perplexity Sonar can give
more accurate, setup-specific advice.
"""

# ---- Comprehensive knowledge fed into the AI system prompt ----

TUNING_KNOWLEDGE = """
=== PRO LATE MODEL OVAL TRACK TUNING REFERENCE ===

--- HANDLING SYMPTOMS & PRIMARY FIXES ---

TIGHT / PUSHES IN CENTER:
- Lower J-bar height (both ends together) to reduce roll angle and improve weight transfer
- Add right rear weight or stiffen RR spring 25-50 lbs to improve rear traction
- Lower rear bar angle (pinion angle) for better mechanical grip through center
- Soften RF spring 25-50 lbs to free up front end
- Add LR bite by raising panhard bar on left side
- Reduce cross-weight 0.2-0.5%
- Increase LR rebound 1-2 clicks
- Key: center handling depends on frontend geometry and weight distribution
- Moment center location: 8-16 inches left of centerline for dirt late models

LOOSE OFF CORNER:
- Stiffen RR spring 25-50 lbs to add rear lateral grip on exit
- Lower panhard bar on right side to increase rear roll resistance
- Add cross-weight 0.2-0.5% to load the RR
- Increase RR rebound 1-2 clicks to slow weight transfer off RR
- Raise rear ride height slightly to add rear grip
- Check RR shock rebound - may need more

TIGHT ON ENTRY:
- Soften RF shock compression 1-2 clicks to allow faster front weight transfer
- Reduce LF spring rate 25 lbs to improve front roll on entry
- Increase front stagger slightly to help nose turn in
- Raise front ride height to promote initial turn-in
- Soften front sway bar if equipped

LOOSE ON ENTRY:
- Stiffen RF shock compression 1-2 clicks to slow front weight transfer
- Add LF spring rate 25 lbs to resist front roll
- Lower rear ride height 1/4 inch to reduce rear grip on initial entry
- Increase front compression damping
- Check brake bias - may need more front

NO FORWARD BITE OFF CORNER:
- Soften RR spring 25-50 lbs to plant rear tires better
- Lower rear ride height to improve mechanical traction
- Check LR shock rebound - may be too stiff, preventing weight transfer
- Increase rear stagger to improve drive off corner
- Lower trailing arm angle to improve forward bite
- Add right rear weight

BOUNCING / UNSTABLE:
- Increase shock rebound all corners 1-2 clicks
- Check for worn or blown shocks
- Raise ride height if bottoming out
- Review spring rates vs track conditions
- Check bump springs for proper gap and rate
- Verify nothing is loose or broken in suspension

--- TRACK CONDITION ADJUSTMENTS ---

DRY/SLICK TRACK:
- Soften springs overall to maintain mechanical grip
- Increase rebound damping to control weight transfer
- Lower ride heights to lower center of gravity
- May need more rear stagger
- Cross-weight becomes more critical

TACKY/HEAVY TRACK:
- Stiffen springs to handle higher loads
- Reduce rebound damping slightly
- Raise ride heights for more suspension travel
- Less rear stagger needed
- Aero devices more effective

WET TRACK:
- Maximum mechanical grip setup
- Softest spring package
- Increase all shock rebound
- Lower center of gravity as much as possible
- Reduce stagger

--- SETUP FUNDAMENTALS ---

SPRINGS:
- Typical Pro Late Model range: 150-350 lbs/in per corner
- RF usually softest, LR usually stiffest
- Split between front springs affects entry handling
- Split between rear springs affects exit handling
- Rule of thumb: change springs in 25 lb increments

SHOCKS:
- Compression controls how fast weight transfers TO a corner
- Rebound controls how fast weight transfers AWAY from a corner
- Entry handling: adjust front compression and rear rebound
- Exit handling: adjust rear compression and front rebound
- Rule of thumb: change 1-2 clicks at a time

WEIGHT DISTRIBUTION:
- Typical left side: 53-57%
- Typical rear: 52-56%
- Cross-weight (diagonal): 49-52% typical
- Adding left = more entry grip, less exit
- Adding rear = more forward bite, can loosen entry

RIDE HEIGHTS:
- Affects center of gravity and weight transfer rate
- Lower = faster transfer, more responsive
- Higher = slower transfer, more stable
- Typical adjustments: 1/4 inch at a time
- Front higher than rear = looser entry
- Rear higher than front = tighter entry

TRACK BAR / J-BAR / PANHARD BAR:
- Controls rear roll center height
- Lower = less rear grip, car rolls more
- Higher = more rear grip, car rolls less
- Left side height controls rear grip in center of turn
- Right side height controls rear grip on entry/exit
- Lower both ends = tighter in center
- Raise both ends = looser in center

TRAILING ARM:
- Controls rear axle pinion angle
- Lower angle = more forward bite off corner
- Higher angle = less forward bite, more stable
- Typical adjustment: 1/2 degree at a time

STAGGER:
- Difference between right and left tire circumference
- More stagger = car turns easier
- Less stagger = car drives straighter
- Too much = loose off corner, eats right rear tire
- Too little = pushes through entire corner
- Typical range: 1/2 to 2 inches

GEAR RATIO:
- Lower ratio (higher number) = more acceleration, lower top speed
- Higher ratio (lower number) = less acceleration, higher top speed
- Match to track size and banking

SWAY BAR:
- Connects left and right side of front suspension
- Stiffer bar = less front roll = tighter
- Softer bar = more front roll = looser
- Disconnecting = maximum front roll
"""


def get_tuning_knowledge():
    """Return the full tuning knowledge base string for AI context."""
    return TUNING_KNOWLEDGE


def get_symptom_knowledge(symptom):
    """Return specific knowledge section for a given symptom."""
    sections = {
        "Tight / Pushes in center": "TIGHT / PUSHES IN CENTER",
        "Loose off corner": "LOOSE OFF CORNER",
        "Tight on entry": "TIGHT ON ENTRY",
        "Loose on entry": "LOOSE ON ENTRY",
        "No forward bite off corner": "NO FORWARD BITE OFF CORNER",
        "Bouncing / Unstable": "BOUNCING / UNSTABLE",
    }
    header = sections.get(symptom, "")
    if not header:
        return ""
    # Extract the relevant section from the knowledge base
    start = TUNING_KNOWLEDGE.find(header + ":")
    if start == -1:
        return ""
    # Find the next section header (starts with newline + uppercase)
    end = TUNING_KNOWLEDGE.find("\n\n", start + len(header))
    if end == -1:
        end = len(TUNING_KNOWLEDGE)
    return TUNING_KNOWLEDGE[start:end].strip()
