from typing import List, Tuple, Union

import numpy as np
import pandas as pd

from detection_dataset.utils.enums import Split


class Dataset:

    COLUMNS = [
        "image_id",
        "bbox_id",
        "category_id",
        "category",
        "supercategory",
        "bbox",
        "width",
        "height",
        "area",
        "image_name",
        "image_path",
        "split",
    ]

    data = pd.DataFrame(columns=COLUMNS).set_index(["image_id", "bbox_id"])

    def __init__(self, data: pd.DataFrame = None) -> None:
        """Initializes the dataset."""

        if data is not None:
            data = data[data.columns.intersection(self.COLUMNS)]
            self.concat(data)

    def concat(self, other_data: pd.DataFrame) -> None:
        """Concatenates the existing data with new data."""

        self.data = pd.concat([self.data, other_data])

    def map_categories(self, mapping: pd.DataFrame) -> None:
        """Maps the categories to the new categories.

        Args:
            category_mapping: A DataFrame mapping original categories to new categories.
                Schema:
                    - category_id: Original category id
                    - category: Original category name
                    - new_category_id: New category id
                    - new_category: New category name
        """

        mapping = mapping.loc[:, ["category_id", "category", "new_category_id", "new_category"]]

        data = (
            self.data.reset_index()
            .merge(mapping, on=["category_id", "category"], how="left", validate="m:1")
            .set_index(["image_id", "bbox_id"])
        )
        data = data[data.new_category_id >= 0]
        self.data = data.rename(
            columns={
                "category_id": "category_id_original",
                "category": "category_original",
                "new_category_id": "category_id",
                "new_category": "category",
            }
        )

    def limit_images(self, n_images: int) -> None:
        """Limits the number of images to n_images.

        Args:
            n_images: Number of images to include in the dataset.
                The original proportion of images between splits will be respected.
        """

        if self.n_images > len(self.data):
            raise ValueError(
                "The number of images to include in the dataset is greater than the number of images present."
            )

        split_data = []
        data_by_image = self.data_by_image

        for split in Split:
            if split.value in data_by_image.split.unique():
                sample_size = int(n_images * self.split_proportions[split.value])
                split_data.append(
                    data_by_image.loc[data_by_image.split == split.value, :].sample(sample_size, random_state=42)
                )

        data = pd.concat(split_data)
        self.data = self.explode(data)

    def split(self, splits: Tuple[Union[int, float]]) -> None:
        """Splits the dataset into train, val and test.

        Args:
            splits: Iterable containing the proportion of images to include in the train, val and test splits.
                The sum of the values in the iterable must be equal to 1. The original splits will be overwritten.
        """

        if len(splits) != 3:
            raise ValueError(f"The splits must be a tuple of 3 elements, here it is: {splits}.")

        if sum(splits) != 1:
            raise ValueError(f"The sum of the proportion for each split must be equal to 1, here it is: {sum(splits)}.")

        if not all([isinstance(x, float) for x in splits]):
            raise TypeError("Splits must be either int or float, here it is: {}.".format(*[type(s) for s in splits]))

        data_by_image = self.data_by_image.copy()

        n_train = int(splits[0] * len(data_by_image))
        n_val = int(n_train + splits[1] * len(data_by_image))
        n_test = int(n_val + splits[2] * len(data_by_image))

        data_by_image = data_by_image.sample(frac=1, random_state=42)
        data_train, data_val, data_test, _ = np.split(data_by_image, [n_train, n_val, n_test])
        data_train["split"] = Split.TRAIN.value
        data_val["split"] = Split.VAL.value
        data_test["split"] = Split.TEST.value

        data = pd.concat([data_train, data_val, data_test])
        self.data = self.explode(data)

    @property
    def data_by_image(self) -> pd.DataFrame:
        """Returns the data grouped by image.

        Returns:
            A DataFrame grouped by image, meaning that each may contain data related to multiple bboxes.
        """

        data = self.data.reset_index().groupby("image_id")
        return pd.DataFrame(
            {
                "bbox_id": data["bbox_id"].apply(list),
                "category_id": data["category_id"].apply(list),
                "category": data["category"].apply(list),
                "supercategory": data["supercategory"].apply(list),
                "bbox": data["bbox"].apply(list),
                "width": data["width"].first(),
                "height": data["height"].first(),
                "area": data["area"].apply(list),
                "image_name": data["image_name"].first(),
                "image_path": data["image_path"].first(),
                "split": data["split"].first(),
            }
        ).reset_index()

    def explode(self, data: pd.DataFrame) -> pd.DataFrame:
        """Converts a DataFrame arranged by image to a DataFrame arranged by bbox.

        This method reverses the effect of calling self.data_by_image.

        Args:
            data: Dataframe to explode.

        Returns:
            A DataFrame arranged by bbox instead of images.
        """

        return data.explode(["bbox_id", "category_id", "category", "supercategory", "area", "bbox"]).set_index(
            ["image_id", "bbox_id"]
        )

    @property
    def n_images(self) -> int:
        """Returns the number of images in the dataset.

        Returns:
            The number of images in the dataset.
        """

        return len(self.data_by_image)

    @property
    def splits(self) -> List[str]:
        """Returns the splits of the dataset.

        Returns:
            The splits present in the dataset.
        """

        return self.data.split.unique().tolist()

    @property
    def split_proportions(self) -> Tuple[float, float, float]:
        """Returns the proportion of images in the train, val and test splits.

        Returns:
            The proportion of images in the train, val and test splits.
        """

        data = self.data.copy()
        return pd.DataFrame({s.value: [len(data[data.split == s.value]) / len(data)] for s in Split})

    @property
    def categories(self) -> None:
        """Creates a DataFrame containing the categories found in the data with their id."""

        return (
            self.data.loc[:, ["category_id", "category", "supercategory"]]
            .drop_duplicates()
            .sort_values("category_id")
            .reset_index(drop=True)
        )

    @property
    def category_names(self) -> List[str]:
        """Returns the categories names.

        Returns:
            The categories names.
        """

        return self.categories.category.unique()

    @property
    def n_categories(self) -> int:
        """Returns the number of categories.

        Returns:
            The number of categories.
        """

        return self.categories.category.nunique()
