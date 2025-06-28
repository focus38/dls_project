import torch
import torch.nn as nn

class CRNN(nn.Module):
    def __init__(self, num_channels, num_chars, hidden_size=256):
        super(CRNN, self).__init__()
        self.num_chars = num_chars
        self.hidden_size = hidden_size

        self.cnn = nn.Sequential(
            nn.Conv2d(num_channels, 64, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(2, 2), stride=2),

            nn.Conv2d(64, 128, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(2, 2), stride=2),

            nn.Conv2d(128, 256, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(num_features=256),

            nn.Conv2d(256, 256, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(1, 2), stride=2),

            nn.Conv2d(256, 512, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(num_features=512),

            nn.Conv2d(512, 512, kernel_size=(3, 3), stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(num_features=512),
            nn.MaxPool2d(kernel_size=(1, 2), stride=2),

            nn.Conv2d(512, 512, kernel_size=(2, 2), stride=1, padding=0),
            nn.ReLU(inplace=True),
        )

        self.lstm = nn.LSTM(input_size=512, hidden_size=self.hidden_size, num_layers=2, bidirectional=True, dropout=0.2)
        self.fc = nn.Linear(self.hidden_size * 2, self.num_chars)  # x2 из-за конкатенации

    def forward(self, x: torch.Tensor): # (B, C, H, W)
        features = self.cnn(x)  # (B, C, H, W)
        B, C, H, W = features.size()
        T = H * W
        lstm_input = features.view(B, C, T)  # (B, C, T)
        lstm_input = lstm_input.permute(2, 0, 1)  # (T, B, C)
        lstm_output, _ = self.lstm(lstm_input)  # (T, B, 2 * hidden_size)
        # Конкатенация направлений вместо суммирования
        lstm_output = lstm_output.view(T, B, 2, self.hidden_size)  # (T, B, 2, hidden_size)
        fc_input = torch.cat([lstm_output[:, :, 0], lstm_output[:, :, 1]], dim=2)  # (T, B, 2*hidden_size)
        
        ocr_output = self.fc(fc_input)

        scaled_h = H // 16
        scaled_w = W // 4
        encoder_out_lens = torch.full((B,), fill_value=scaled_h * scaled_w, device=x.device)
        return ocr_output, encoder_out_lens # [T, B, num_chars], [B, L]
