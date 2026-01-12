import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision
import torchvision.transforms as transforms
from torchvision.datasets import ImageFolder
import timm

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
from tqdm import tqdm

from pathlib import Path

print('System Version:', sys.version)
print('PyTorch version', torch.__version__)
print('Torchvision version', torchvision.__version__)
print('Numpy version', np.__version__)
print('Pandas version', pd.__version__)

class PlayingCardsDataSet(Dataset):
  def __init__(self, data_dir, transform=None):
    self.data = ImageFolder(data_dir, transform=transform)
  
  def __len__(self):
    return len(self.data)
  
  def __getitem__(self, idx):
    return self.data[idx]
  
  @property
  def classes(self):
    return self.data.classes

class SimpleCardClassifier(nn.Module):
  def __init__(self, num_classes=53):
    super(SimpleCardClassifier, self).__init__()
    # Definiera alla delar av modellen
    self.base_model = timm.create_model('efficientnet_b0', pretrained=True)
    self.features = nn.Sequential(*list(self.base_model.children())[:-1])

    enet_out_size = 1280

    # Skapa en classifier
    self.classifier = nn.Linear(enet_out_size, num_classes)

  def forward(self, x):
    # Koppla samman alla delar och retunera outputen
    x = self.features(x)
    output = self.classifier(x)
    return output


transform = transforms.Compose([
  transforms.Resize((128, 128)),
  transforms.ToTensor(),
])

dir = Path(__file__).parent

train_folder = dir / 'dataset_spelkort' / 'train'
valid_folder = dir / 'dataset_spelkort' / 'valid'
test_folder = dir / 'dataset_spelkort' / 'test'

train_dataset = PlayingCardsDataSet(train_folder, transform=transform)
valid_dataset = PlayingCardsDataSet(valid_folder, transform=transform)
test_dataset = PlayingCardsDataSet(test_folder, transform=transform)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
valid_loader = DataLoader(valid_dataset, batch_size=32, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)


num_epochs = 5 # En epoch är en körning genom hela datasettet
train_losses, val_losses = [], []

model = SimpleCardClassifier(num_classes=53)

# Loss function
criterion = nn.CrossEntropyLoss()
# Optimiser
optimiser = optim.Adam(model.parameters(), lr=0.001)

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)
model.to(device)

for epoch in range(num_epochs):
  # Träna modellen
  model.train()
  running_loss = 0.0
  
  for images, labels in tqdm(train_loader, desc='Training loop'):
    images, labels = images.to(device), labels.to(device)
    optimiser.zero_grad()
    outputs = model(images)
    loss = criterion(outputs, labels)
    loss.backward()
    optimiser.step()
    running_loss += loss.item() * labels.size(0)
  train_loss = running_loss / len(train_loader.dataset)
  train_losses.append(train_loss)

  # Validering
  model.eval()
  running_loss = 0.0
  with torch.no_grad():
    for images, labels in tqdm(valid_loader, desc='Validation loop'):
      images, labels = images.to(device), labels.to(device)
      outputs = model(images)
      loss = criterion(outputs, labels)
      running_loss += loss.item() * labels.size(0)
  
  val_loss = running_loss / len(valid_loader.dataset)
  val_losses.append(val_loss)
  print(f"Epoch {epoch+1}/{num_epochs} - Train loss: {train_loss}, Validation loss: {val_loss}")