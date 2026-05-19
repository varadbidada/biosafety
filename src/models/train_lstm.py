import os
import json
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
MODELS_PATH = os.path.join(ROOT, "models")
os.makedirs(MODELS_PATH, exist_ok=True)

print("Loading dataset:", DATA_PATH)
df = pd.read_csv(DATA_PATH).dropna()

feature_cols = json.load(open(os.path.join(MODELS_PATH, "feature_cols.json")))
INPUT_SIZE = len(feature_cols)

X = df[feature_cols].values
y = df["target_cases_next"].values

# Scaling
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_t = torch.tensor(X_scaled, dtype=torch.float32).reshape(-1, 1, INPUT_SIZE)
y_t = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)

dataset = TensorDataset(X_t, y_t)
loader = DataLoader(dataset, batch_size=64, shuffle=True)

class LSTMModel(nn.Module):
    def __init__(self, input_size):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=96, num_layers=2, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(96, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

model = LSTMModel(INPUT_SIZE)
opt = torch.optim.Adam(model.parameters(), lr=0.001)
loss_fn = nn.MSELoss()

print("Training LSTM (High Accuracy)...")
for epoch in range(40):
    losses = []
    for xb, yb in loader:
        opt.zero_grad()
        pred = model(xb)
        loss = loss_fn(pred, yb)
        loss.backward()
        opt.step()
        losses.append(loss.item())
    print(f"Epoch {epoch+1}/40  loss={np.mean(losses):.4f}")

torch.save(model.state_dict(), os.path.join(MODELS_PATH, "lstm_model_full.pt"))
joblib.dump(scaler, os.path.join(MODELS_PATH, "lstm_scaler.pkl"))

print("✓ LSTM model saved!")