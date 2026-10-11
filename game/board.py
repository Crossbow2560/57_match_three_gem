import math
import random
import pygame

GRID_SIZE = 8
TILE_SIZE = 60
GEM_COLORS = [
    (220, 50, 50),   # Red
    (50, 200, 50),   # Green
    (50, 100, 240),  # Blue
    (240, 200, 40),  # Yellow
    (180, 50, 220),  # Purple
    (240, 130, 40),  # Orange
]


class Gem:
   
    def __init__(self, color, target_row, col):
        self.color = color
        self.target_row = target_row
        self.col = col
        self.current_y = (target_row - 2) * TILE_SIZE
        self.target_y = target_row * TILE_SIZE
        self.fall_speed = 12.0
        self.special = None  # None, "row" or "col": line this gem clears when matched

    def update(self):
        if self.current_y < self.target_y:
            self.current_y += self.fall_speed
            if self.current_y > self.target_y:
                self.current_y = self.target_y

    def is_animating(self):
        return self.current_y < self.target_y


class Board:

    def __init__(self, offset_x, offset_y, target_score=500, max_moves=20):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.target_score = target_score
        self.max_moves = max_moves
        self.grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.selected = None
        self.score = 0
        self.moves_remaining = max_moves
        self.last_combo = 0
        self.blasts = []
        self.reset()

    def reset(self):
        self.score = 0
        self.moves_remaining = self.max_moves
        self.selected = None
        self.blasts = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                color = random.choice(GEM_COLORS)
                gem = Gem(color, r, c)
                gem.current_y = gem.target_y  
                self.grid[r][c] = gem

        self.resolve_matches(allow_specials=False)
        self.last_combo = 0

    def is_animating(self):
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c] and self.grid[r][c].is_animating():
                    return True
        return False

    def swap_gems(self, pos1, pos2):
        r1, c1 = pos1
        r2, c2 = pos2

        g1, g2 = self.grid[r1][c1], self.grid[r2][c2]
        self.grid[r1][c1], self.grid[r2][c2] = g2, g1

        if self.grid[r1][c1]:
            self.grid[r1][c1].target_row = r1
            self.grid[r1][c1].target_y = r1 * TILE_SIZE
            self.grid[r1][c1].current_y = r1 * TILE_SIZE

        if self.grid[r2][c2]:
            self.grid[r2][c2].target_row = r2
            self.grid[r2][c2].target_y = r2 * TILE_SIZE
            self.grid[r2][c2].current_y = r2 * TILE_SIZE

    def is_adjacent(self, pos1, pos2):
        r1, c1 = pos1
        r2, c2 = pos2
        return abs(r1 - r2) + abs(c1 - c2) == 1

    def find_runs(self):
        runs = []

        for r in range(GRID_SIZE):
            c = 0
            while c < GRID_SIZE:
                end = c + 1
                gem = self.grid[r][c]
                while gem and end < GRID_SIZE and self.grid[r][end] and self.grid[r][end].color == gem.color:
                    end += 1
                if gem and end - c >= 3:
                    runs.append(("row", [(r, k) for k in range(c, end)]))
                c = end

        for c in range(GRID_SIZE):
            r = 0
            while r < GRID_SIZE:
                end = r + 1
                gem = self.grid[r][c]
                while gem and end < GRID_SIZE and self.grid[end][c] and self.grid[end][c].color == gem.color:
                    end += 1
                if gem and end - r >= 3:
                    runs.append(("col", [(k, c) for k in range(r, end)]))
                r = end

        return runs

    def find_matches(self):
        matched = set()
        for _, cells in self.find_runs():
            matched.update(cells)
        return matched

    def pick_special_spot(self, cells, swapped, taken):
        for pos in swapped:
            if pos in cells and pos not in taken and not self.grid[pos[0]][pos[1]].special:
                return pos
        candidates = [
            p for p in cells if p not in taken and not self.grid[p[0]][p[1]].special
        ]
        return candidates[len(candidates) // 2] if candidates else None

    def expand_detonations(self, cells, protected):
        to_clear = set(cells)
        pending = [p for p in to_clear if self.grid[p[0]][p[1]].special]
        detonated = set()
        while pending:
            r, c = pending.pop()
            if (r, c) in detonated:
                continue
            detonated.add((r, c))
            kind = self.grid[r][c].special
            if kind == "row":
                line = [(r, k) for k in range(GRID_SIZE)]
                self.blasts.append(("row", r, pygame.time.get_ticks()))
            else:
                line = [(k, c) for k in range(GRID_SIZE)]
                self.blasts.append(("col", c, pygame.time.get_ticks()))
            for p in line:
                if p in protected or p in to_clear:
                    continue
                to_clear.add(p)
                if self.grid[p[0]][p[1]].special:
                    pending.append(p)
        return to_clear

    def drop_and_refill(self):
        for c in range(GRID_SIZE):
            empty_slots = 0
            for r in range(GRID_SIZE - 1, -1, -1):
                if self.grid[r][c] is None:
                    empty_slots += 1
                elif empty_slots > 0:
                    gem = self.grid[r][c]
                    gem.target_row = r + empty_slots
                    gem.target_y = (r + empty_slots) * TILE_SIZE
                    self.grid[r + empty_slots][c] = gem
                    self.grid[r][c] = None

            for r in range(empty_slots):
                color = random.choice(GEM_COLORS)
                gem = Gem(color, r, c)
                gem.current_y = -((empty_slots - r) * TILE_SIZE)
                self.grid[r][c] = gem

    def resolve_matches(self, swapped=(), allow_specials=True):
        points = 0
        combo = 0
        while True:
            runs = self.find_runs()
            if not runs:
                break
            combo += 1

            matches = set()
            for _, cells in runs:
                matches.update(cells)

            new_specials = {}
            if allow_specials:
                for kind, cells in runs:
                    if len(cells) >= 4:
                        spot = self.pick_special_spot(cells, swapped, new_specials)
                        if spot:
                            new_specials[spot] = kind

            to_clear = self.expand_detonations(matches - new_specials.keys(), new_specials)
            points += len(to_clear) * 10 * combo
            for r, c in to_clear:
                self.grid[r][c] = None
            for (r, c), kind in new_specials.items():
                self.grid[r][c].special = kind

            self.drop_and_refill()
            swapped = ()
        self.last_combo = combo
        return points

    def process_swap(self, pos1, pos2):
        if not self.is_adjacent(pos1, pos2) or self.is_game_over() or self.is_animating():
            return False

        self.swap_gems(pos1, pos2)
        matches = self.find_matches()

        if matches:
            self.moves_remaining -= 1

        else:
            self.swap_gems(pos1, pos2)
            return False

        self.score += self.resolve_matches(swapped=(pos1, pos2))
        return True

    def is_game_over(self):
        return self.score >= self.target_score or self.moves_remaining <= 0

    def check_result(self):
        if self.score >= self.target_score:
            return "WIN"
        if self.moves_remaining <= 0:
            return "LOSS"
        return None

    def update(self):
        now = pygame.time.get_ticks()
        self.blasts = [b for b in self.blasts if now - b[2] < 400]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c]:
                    self.grid[r][c].update()

    def render(self, surface):
        board_rect = pygame.Rect(
            self.offset_x, self.offset_y, GRID_SIZE * TILE_SIZE, GRID_SIZE * TILE_SIZE
        )
        pygame.draw.rect(surface, (20, 22, 28), board_rect, border_radius=8)
        pygame.draw.rect(surface, (60, 65, 75), board_rect, width=3, border_radius=8)

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                gem = self.grid[r][c]
                if gem:
                    x = self.offset_x + c * TILE_SIZE
                    y = self.offset_y + gem.current_y
                    tile_rect = pygame.Rect(x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4)

                    pygame.draw.rect(surface, gem.color, tile_rect, border_radius=10)
                    pygame.draw.rect(
                        surface, (255, 255, 255), tile_rect, width=1, border_radius=10
                    )
                    if gem.special:
                        self.render_special(surface, gem, tile_rect)

                if self.selected == (r, c):
                    sel_x = self.offset_x + c * TILE_SIZE
                    sel_y = self.offset_y + r * TILE_SIZE
                    sel_rect = pygame.Rect(sel_x + 2, sel_y + 2, TILE_SIZE - 4, TILE_SIZE - 4)
                    pygame.draw.rect(
                        surface, (255, 255, 255), sel_rect, width=4, border_radius=10
                    )

        now = pygame.time.get_ticks()
        for kind, index, start in self.blasts:
            alpha = max(0, int(200 * (1 - (now - start) / 400)))
            if kind == "row":
                rect = pygame.Rect(self.offset_x, self.offset_y + index * TILE_SIZE, GRID_SIZE * TILE_SIZE, TILE_SIZE)
            else:
                rect = pygame.Rect(self.offset_x + index * TILE_SIZE, self.offset_y, TILE_SIZE, GRID_SIZE * TILE_SIZE)
            flash = pygame.Surface(rect.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, alpha))
            surface.blit(flash, rect.topleft)

    def render_special(self, surface, gem, tile_rect):
        pulse = (math.sin(pygame.time.get_ticks() / 150) + 1) / 2
        glow = tuple(int(ch + (255 - ch) * (0.4 + 0.6 * pulse)) for ch in gem.color)

        inner = tile_rect.inflate(-16, -16)
        for i in range(3):
            if gem.special == "row":
                y = inner.top + i * inner.height // 2
                pygame.draw.line(surface, glow, (inner.left, y), (inner.right, y), 3)
            else:
                x = inner.left + i * inner.width // 2
                pygame.draw.line(surface, glow, (x, inner.top), (x, inner.bottom), 3)

        pygame.draw.rect(surface, glow, tile_rect, width=3, border_radius=10)
