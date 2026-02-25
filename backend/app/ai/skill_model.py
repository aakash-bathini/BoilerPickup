"""
Embedding-based skill model for pickup basketball.

Architecture:
  - Each player has a learnable 16-dim embedding E_i
  - Per-game stat vector x_i (12-dim) is projected: h_i = W * x_i
  - Team representation: T = mean(E_i + h_i) for all i in team
  - Win probability: P(A wins) = sigmoid(MLP(T_A - T_B))
  - Scalar skill: S_i = ||E_i||_2 scaled to [1, 10]
"""
import os
import math
import torch
import torch.nn as nn
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "model.pt")
EMBEDDING_DIM = 16
STAT_DIM = 12  # 9 stats + 3 game-type one-hot


class SkillModel(nn.Module):
    def __init__(self, max_players: int = 500):
        super().__init__()
        self.max_players = max_players
        self.embedding_dim = EMBEDDING_DIM

        self.player_embeddings = nn.Embedding(max_players, EMBEDDING_DIM)
        self.stat_projection = nn.Linear(STAT_DIM, EMBEDDING_DIM, bias=False)

        self.win_predictor = nn.Sequential(
            nn.Linear(EMBEDDING_DIM, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

        self.skill_init_layer = nn.Linear(1, EMBEDDING_DIM)

        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.player_embeddings.weight, mean=0, std=0.1)
        nn.init.xavier_uniform_(self.stat_projection.weight)
        for m in self.win_predictor:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def initialize_player_embedding(self, player_id: int, self_reported_skill: float):
        """Map self-reported skill (1-10) to initial embedding."""
        with torch.no_grad():
            skill_tensor = torch.tensor([[self_reported_skill / 10.0]])
            init_emb = self.skill_init_layer(skill_tensor).squeeze(0)
            scale = self_reported_skill / 10.0
            init_emb = init_emb * scale
            if player_id < self.max_players:
                self.player_embeddings.weight.data[player_id] = init_emb

    def compute_stat_features(
        self, raw_stats: dict, team_totals: dict, game_type: str
    ) -> torch.Tensor:
        """
        Build 12-dim feature vector from raw stats.

        raw_stats keys: pts, reb, ast, stl, blk, tov, fgm, fga, three_pm, three_pa, ftm, fta
        team_totals keys: pts, reb, ast
        game_type: "5v5", "3v3", or "2v2"
        """
        pts_norm = raw_stats["pts"] / max(team_totals["pts"], 1)
        reb_norm = raw_stats["reb"] / max(team_totals["reb"], 1)
        ast_norm = raw_stats["ast"] / max(team_totals["ast"], 1)

        fg_eff = (raw_stats["fgm"] + 1) / (raw_stats["fga"] + 2)
        three_eff = (raw_stats["three_pm"] + 1) / (raw_stats["three_pa"] + 2)
        ft_eff = (raw_stats["ftm"] + 1) / (raw_stats["fta"] + 2)

        game_type_vec = [0.0, 0.0, 0.0]
        if game_type == "5v5":
            game_type_vec[0] = 1.0
        elif game_type == "3v3":
            game_type_vec[1] = 1.0
        elif game_type == "2v2":
            game_type_vec[2] = 1.0

        features = [
            pts_norm, reb_norm, ast_norm,
            float(raw_stats["stl"]), float(raw_stats["blk"]), float(raw_stats["tov"]),
            fg_eff, three_eff, ft_eff,
        ] + game_type_vec

        return torch.tensor(features, dtype=torch.float32)

    def forward(
        self,
        team_a_ids: torch.Tensor,
        team_b_ids: torch.Tensor,
        team_a_stats: torch.Tensor,
        team_b_stats: torch.Tensor,
    ) -> torch.Tensor:
        """
        Predict P(team A wins).

        team_a_ids: (n_a,) player indices
        team_b_ids: (n_b,) player indices
        team_a_stats: (n_a, 12) stat vectors
        team_b_stats: (n_b, 12) stat vectors
        """
        emb_a = self.player_embeddings(team_a_ids)
        emb_b = self.player_embeddings(team_b_ids)

        proj_a = self.stat_projection(team_a_stats)
        proj_b = self.stat_projection(team_b_stats)

        team_rep_a = (emb_a + proj_a).mean(dim=0)
        team_rep_b = (emb_b + proj_b).mean(dim=0)

        diff = team_rep_a - team_rep_b
        logit = self.win_predictor(diff)
        return torch.sigmoid(logit).squeeze(-1)

    def get_player_skill(self, player_id: int) -> float:
        """Extract scalar skill from embedding L2 norm, scaled to [1, 10]."""
        with torch.no_grad():
            if player_id >= self.max_players:
                return 5.0
            emb = self.player_embeddings.weight[player_id]
            raw = torch.norm(emb, p=2).item()
            scaled = 1.0 + 9.0 * (1.0 - math.exp(-raw / 2.0))
            return round(min(max(scaled, 1.0), 10.0), 2)

    def predict_win_probability(
        self,
        team_a_ids: list[int],
        team_b_ids: list[int],
    ) -> float:
        """Quick win probability using embeddings only (no stats)."""
        with torch.no_grad():
            a_ids = torch.tensor(team_a_ids, dtype=torch.long)
            b_ids = torch.tensor(team_b_ids, dtype=torch.long)
            emb_a = self.player_embeddings(a_ids).mean(dim=0)
            emb_b = self.player_embeddings(b_ids).mean(dim=0)
            diff = emb_a - emb_b
            logit = self.win_predictor(diff)
            return torch.sigmoid(logit).squeeze(-1).item()

    def save(self, path: str = MODEL_PATH):
        torch.save(self.state_dict(), path)

    def load(self, path: str = MODEL_PATH):
        if os.path.exists(path):
            self.load_state_dict(torch.load(path, weights_only=True))


_model_instance: SkillModel | None = None


def get_model() -> SkillModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = SkillModel()
        if os.path.exists(MODEL_PATH):
            _model_instance.load()
    return _model_instance


def train_on_games(games_data: list[dict], epochs: int = 50, lr: float = 1e-3) -> dict:
    """
    Train the model on game data.

    Each game_data dict:
        team_a_ids: list[int]
        team_b_ids: list[int]
        team_a_stats: list[list[float]]  (each player's 12-dim stat vector)
        team_b_stats: list[list[float]]
        team_a_won: bool
    """
    model = get_model()
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCELoss()

    losses = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        correct = 0
        total = 0

        for game in games_data:
            a_ids = torch.tensor(game["team_a_ids"], dtype=torch.long)
            b_ids = torch.tensor(game["team_b_ids"], dtype=torch.long)
            a_stats = torch.tensor(game["team_a_stats"], dtype=torch.float32)
            b_stats = torch.tensor(game["team_b_stats"], dtype=torch.float32)
            label = torch.tensor(1.0 if game["team_a_won"] else 0.0)

            pred = model(a_ids, b_ids, a_stats, b_stats)
            loss = criterion(pred, label)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            predicted_winner = pred.item() > 0.5
            actual_winner = game["team_a_won"]
            if predicted_winner == actual_winner:
                correct += 1
            total += 1

        avg_loss = epoch_loss / max(len(games_data), 1)
        accuracy = correct / max(total, 1)
        losses.append(avg_loss)

    model.save()
    model.eval()

    return {
        "final_loss": losses[-1] if losses else 0.0,
        "final_accuracy": accuracy,
        "epochs": epochs,
        "num_games": len(games_data),
    }


if __name__ == "__main__":
    print("SkillModel architecture:")
    model = SkillModel()
    print(model)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nTotal parameters: {total_params:,}")
