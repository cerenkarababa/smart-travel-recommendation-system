
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.model_selection import GroupShuffleSplit


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DATA_FILE = (
    BASE_DIR / "data" / "processed" / "training_data.joblib"
)

MODEL_DIR = BASE_DIR / "models"
MODEL_FILE = MODEL_DIR / "random_forest_model.joblib"


def load_processed_data():
    """Load the preprocessed dataset."""

    if not PROCESSED_DATA_FILE.exists():
        raise FileNotFoundError(
            "Processed dataset not found. "
            "Run data preprocessing first."
        )

    processed_data = joblib.load(PROCESSED_DATA_FILE)

    X = processed_data["X"]
    y = processed_data["y"]
    metadata = processed_data["metadata"]

    print("Processed dataset loaded successfully.")
    print(f"Number of records: {X.shape[0]:,}")
    print(f"Number of features: {X.shape[1]:,}")

    return X, y, metadata


def split_dataset(X, y, metadata):
    """Split the dataset while keeping each user in one group."""

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42,
    )

    train_indices, test_indices = next(
        splitter.split(
            X,
            y,
            groups=metadata["user_id"],
        )
    )

    X_train = X[train_indices]
    X_test = X[test_indices]

    y_train = y[train_indices]
    y_test = y[test_indices]

    metadata_test = metadata.iloc[test_indices].reset_index(drop=True)

    train_users = set(metadata.iloc[train_indices]["user_id"])
    test_users = set(metadata.iloc[test_indices]["user_id"])

    if train_users.intersection(test_users):
        raise ValueError(
            "Data leakage detected: a user appears in both datasets."
        )

    print("\nDataset split completed.")
    print(f"Training records: {len(train_indices):,}")
    print(f"Testing records: {len(test_indices):,}")
    print(f"Training users: {len(train_users):,}")
    print(f"Testing users: {len(test_users):,}")

    return X_train, X_test, y_train, y_test, metadata_test


def train_model(X_train, y_train):
    """Train a Random Forest classification model."""

    print("\nStarting Random Forest training...")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=20,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    print("Model training completed.")

    return model


def evaluate_model(model, X_test, y_test):
    """Calculate and display classification performance metrics."""

    print("\nEvaluating model...")

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    precision = precision_score(
        y_test,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        y_test,
        predictions,
        zero_division=0,
    )

    f1 = f1_score(
        y_test,
        predictions,
        zero_division=0,
    )

    error_rate = 1 - accuracy

    metrics = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "error_rate": error_rate,
    }

    print("\nModel Performance")
    print("-" * 35)

    print(f"Accuracy:   {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print(f"Precision:  {precision:.4f} ({precision * 100:.2f}%)")
    print(f"Recall:     {recall:.4f} ({recall * 100:.2f}%)")
    print(f"F1-score:   {f1:.4f} ({f1 * 100:.2f}%)")
    print(f"Error rate: {error_rate:.4f} ({error_rate * 100:.2f}%)")

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=[0, 1],
    )

    print("\nConfusion Matrix")
    print("Rows: Actual labels | Columns: Predicted labels")
    print(matrix)

    return metrics, predictions


def save_model(model, metrics):
    """Save the trained model and evaluation metrics."""

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_data = {
        "model": model,
        "metrics": metrics,
    }

    joblib.dump(
        model_data,
        MODEL_FILE,
        compress=3,
    )

    print(f"\nModel saved to: {MODEL_FILE}")


def main():
    """Run the complete model training and evaluation workflow."""

    print("Starting model training workflow...")

    X, y, metadata = load_processed_data()

    X_train, X_test, y_train, y_test, metadata_test = split_dataset(
        X,
        y,
        metadata,
    )

    model = train_model(X_train, y_train)

    metrics, predictions = evaluate_model(
        model,
        X_test,
        y_test,
    )

    save_model(model, metrics)

    print("\nModel training workflow completed successfully!")


if __name__ == "__main__":
    main()
