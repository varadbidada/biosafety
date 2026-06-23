import os
import json
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from src.models.lstm_model import LSTMModel

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
MODELS_PATH = os.path.join(ROOT, "models")
SEQ_LEN = 10
BATCH_SIZE = 256
EPOCHS = 15
HIDDEN_SIZE = 96
NUM_LAYERS = 2
DROPOUT = 0.2
LEARNING_RATE = 0.001

os.makedirs(MODELS_PATH, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")


class SequenceDataset(Dataset):
    def __init__(self, sequences, targets):
        self.sequences = torch.tensor(sequences, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]


def create_sequences(df, feature_cols, seq_len):
    """Create sliding window sequences per district for time-series (vectorized)."""
    sequences, targets = [], []

    for district, g in df.groupby("district"):
        g = g.sort_values("week_start").reset_index(drop=True)
        values = g[feature_cols].values
        target_values = g["target_cases_next"].values

        n = len(g) - seq_len
        if n <= 0:
            continue

        # Pre-allocate for this district
        seqs = np.zeros((n, seq_len, len(feature_cols)))
        for i in range(seq_len):
            seqs[:, i, :] = values[i : n + i]
        sequences.append(seqs)
        targets.append(target_values[seq_len - 1 : n + seq_len - 1])

    return np.vstack(sequences), np.concatenate(targets)


print("Loading dataset:", DATA_PATH)
df = pd.read_csv(DATA_PATH).dropna()
print(f"Dataset shape: {df.shape}")

feature_cols_path = os.path.join(MODELS_PATH, "feature_cols.json")
if not os.path.exists(feature_cols_path):
    feature_cols = [
        "month", "monsoon", "rainfall", "temperature", "ndvi", "cases",
        "rain_lag_1", "ndvi_lag_1", "cases_lag_1",
        "rain_lag_2", "ndvi_lag_2", "cases_lag_2",
        "rain_lag_3", "ndvi_lag_3", "cases_lag_3",
        "rain_3wk_mean", "ndvi_3wk_mean",
    ]
    json.dump(feature_cols, open(feature_cols_path, "w"))
else:
    feature_cols = json.load(open(feature_cols_path))

INPUT_SIZE = len(feature_cols)
print(f"Features: {INPUT_SIZE}, Sequence length: {SEQ_LEN}")

# Create sequences
X_seq, y = create_sequences(df, feature_cols, SEQ_LEN)
print(f"Sequences created: X={X_seq.shape}, y={y.shape}")

# Train/val split (time-series aware: earlier weeks = train, later = val)
split_idx = int(len(X_seq) * 0.8)
X_train, X_val = X_seq[:split_idx], X_seq[split_idx:]
y_train, y_val = y[:split_idx], y[split_idx:]

# Scale per-sample (each sequence is scaled independently)
orig_shape = X_train.shape
X_train_flat = X_train.reshape(-1, INPUT_SIZE)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_flat).reshape(orig_shape)

X_val_flat = X_val.reshape(-1, INPUT_SIZE)
X_val_scaled = scaler.transform(X_val_flat).reshape(X_val.shape)

train_dataset = SequenceDataset(X_train_scaled, y_train)
val_dataset = SequenceDataset(X_val_scaled, y_val)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

model = LSTMModel(INPUT_SIZE, HIDDEN_SIZE, NUM_LAYERS).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
loss_fn = nn.MSELoss()

print(f"Training LSTM (seq_len={SEQ_LEN}, hidden={HIDDEN_SIZE}, layers={NUM_LAYERS})...")
for epoch in range(EPOCHS):
    model.train()
    train_losses = []
    for xb, yb in train_loader:
        xb, yb = xb.to(device), yb.to(device).unsqueeze(1)
        optimizer.zero_grad()
        pred = model(xb)
        loss = loss_fn(pred, yb)
        loss.backward()
        optimizer.step()
        train_losses.append(loss.item())

    model.eval()
    val_losses = []
    with torch.no_grad():
        for xb, yb in val_loader:
            xb, yb = xb.to(device), yb.to(device).unsqueeze(1)
            pred = model(xb)
            loss = loss_fn(pred, yb)
            val_losses.append(loss.item())

    print(f"Epoch {epoch+1}/{EPOCHS}  train_loss={np.mean(train_losses):.4f}  val_loss={np.mean(val_losses):.4f}")

torch.save(model.state_dict(), os.path.join(MODELS_PATH, "lstm_model_full.pt"))
joblib.dump(scaler, os.path.join(MODELS_PATH, "lstm_scaler.pkl"))

print("LSTM model saved!")
