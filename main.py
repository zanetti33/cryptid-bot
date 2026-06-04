from recognition.dataset import dataset_image_path
from recognition.pipeline import image_to_board_state


if __name__ == "__main__":
    # Quick local smoke run using one sample image.
    board = image_to_board_state(dataset_image_path("screenshot_example.png"))
    print(f"Loaded board with {len(board.tiles)} tiles")

