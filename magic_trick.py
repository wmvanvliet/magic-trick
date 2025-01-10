# Import the modules we’ll need.
import random
from psychopy import core, event, gui, visual

from aalto_meg import AaltoMEG

# Show a dialog box to tweak some parameters
experiment_name = "viswordrec"
experiment_info = {
    "Monitor": "zbook",
    "Stimulus width (degrees)": 3,
    "Number of repetitions": 30,
    "Pilot": False,
}
gui_window = gui.DlgFromDict(
    dictionary=experiment_info, sortKeys=False, title=experiment_name
)
if not gui_window.OK:
    core.quit()

monitor = experiment_info["Monitor"]
stimulus_width = experiment_info["Stimulus width (degrees)"]
stimulus_size = (stimulus_width, (stimulus_width / 196) * 273)
n_repetitions = experiment_info["Number of repetitions"]
is_pilot = experiment_info["Pilot"]

# Connect to the equipment in the MEG room.
# When the pilot checkbox is ticked, don't actually try to connect to any hardware,
# but just fake it.
meg = AaltoMEG(fake=is_pilot)

# Define the window.
if is_pilot:
    # Small window to locally test stuff.
    window = visual.Window(
        size=(1024, 720), fullscr=False, color="#696969", monitor=monitor
    )
else:
    # Projector in the MEG room has this as its native resolution.
    window = visual.Window(
        size=(1920, 1080), fullscr=True, color="#696969", monitor=monitor
    )
window.mouseVisible = False  # hide mouse cursor

# Initialize the images
card_images = [
    visual.ImageStim(window, image="cards/card1.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card2.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card3.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card4.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card5.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card6.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card7.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card8.png", size=stimulus_size, units="deg"),
    visual.ImageStim(window, image="cards/card9.png", size=stimulus_size, units="deg"),
]

# Create the instruction screens.
welcome_image = visual.ImageStim(
    window, image="instructions/welcome.png", size=(800, 600), units="pix"
)
counting_image = visual.ImageStim(
    window, image="instructions/counting.png", size=(800, 600), units="pix"
)

cards = [0, 1, 2, 3, 4, 5, 6, 7, 8] * n_repetitions
min_distance = 2

# Determine the order in which the cards are presented. We shuffle and make sure there
# are always at least other cards shown between repetitions of the same card. If not,
# swap the offending card with another card. Keep doing this until all cards are in a
# valid place.
random.shuffle(cards)
swaps_performed = True
while swaps_performed:
    swaps_performed = False
    for i, card in enumerate(cards):
        if card in cards[max(0, i - min_distance) : i]:
            for j in range(i + 1, len(cards) - 1):
                if cards[j] != card:
                    cards[i], cards[j] = cards[j], cards[i]
                    swaps_performed = True


################################################################################
# Start of stimulus presentation.
################################################################################

# Display the instructions and wait for 20 seconds.
welcome_image.draw()
window.flip()
event.waitKeys(maxWait=20, keyList=["space"])  # space option for skipping the wait

counting_image.draw()
window.flip()
event.waitKeys(maxWait=10, keyList=["space"])  # space option for skipping the wait

window.clearBuffer()
window.flip()
core.wait(1)

for i, card in enumerate(cards):
    image = card_images[card]

    # Create clock marking t=0.
    clock = core.Clock()

    # Display the card.
    image.draw()
    window.flip()
    image_onset = clock.getTime()
    meg.send_trigger_code(card + 1)

    # Wait until it is time to clear the scrreen.
    core.wait(0.3 - (clock.getTime() - image_onset))
    window.clearBuffer()
    window.flip()

    # Wait until it is time to display the next card.
    core.wait(0.5 - (clock.getTime() - image_onset))

    # Check if escape was pressed somewhere during the trial. If so, exit experiment.
    response = event.getKeys(keyList=["escape"])
    if len(response) > 0:
        break

    print(f"{i:03d}/{len(cards) - 1:03d}", flush=True)

# Clean up everything.
window.close()
core.quit()
