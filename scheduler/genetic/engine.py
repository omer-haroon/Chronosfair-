"""
Generic Genetic Algorithm engine — reusable across Course / Exam / Invigilation
schedulers (Phases 5, 6 and 7 of the plan).

Design goal: write the GA loop ONCE. Each concrete scheduler (course_ga.py,
exam_ga.py, invigilation_ga.py) only supplies:
  - a way to build a random chromosome
  - a fitness function
  - a repair function (optional)
  - a mutation function

A "chromosome" here is just a list of genes (any hashable/plain-python
object your fitness function understands, usually a small dict or tuple
per unit-to-be-scheduled).
"""
import random
from dataclasses import dataclass, field
from typing import Callable, List, Any, Optional


@dataclass
class GAResult:
    best_chromosome: List[Any]
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    generations_run: int
    converged_at: Optional[int]
    history: List[float] = field(default_factory=list)


class GeneticEngine:
    """
    fitness_fn(chromosome) -> float in [0, 1], where 1.0 = perfect (no violations).
    random_chromosome_fn() -> List[Any]
    crossover_fn(parent_a, parent_b) -> (child_a, child_b)
    mutate_fn(chromosome, mutation_rate) -> chromosome (mutated copy)
    repair_fn(chromosome) -> chromosome (optional; applied every generation to
        the offspring before fitness is recomputed -- this IS the "Repair
        Module" described in the plan: instead of discarding a clashing
        chromosome, we fix it in place).
    """

    def __init__(
        self,
        random_chromosome_fn: Callable[[], List[Any]],
        fitness_fn: Callable[[List[Any]], float],
        crossover_fn: Callable[[List[Any], List[Any]], tuple],
        mutate_fn: Callable[[List[Any], float], List[Any]],
        repair_fn: Optional[Callable[[List[Any]], List[Any]]] = None,
        population_size: int = 60,
        generations: int = 200,
        mutation_rate: float = 0.05,
        crossover_rate: float = 0.80,
        elitism_count: int = 4,
        tournament_size: int = 3,
        convergence_threshold: float = 0.001,
        convergence_patience: int = 20,
        target_fitness: float = 0.999,
        rng: Optional[random.Random] = None,
    ):
        self.random_chromosome_fn = random_chromosome_fn
        self.fitness_fn = fitness_fn
        self.crossover_fn = crossover_fn
        self.mutate_fn = mutate_fn
        self.repair_fn = repair_fn
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_count = elitism_count
        self.tournament_size = tournament_size
        self.convergence_threshold = convergence_threshold
        self.convergence_patience = convergence_patience
        self.target_fitness = target_fitness
        self.rng = rng or random.Random()

    def _tournament_select(self, population, fitnesses):
        contenders = self.rng.sample(range(len(population)), min(self.tournament_size, len(population)))
        best_idx = max(contenders, key=lambda i: fitnesses[i])
        return population[best_idx]

    def run(self) -> GAResult:
        population = [self.random_chromosome_fn() for _ in range(self.population_size)]
        if self.repair_fn:
            population = [self.repair_fn(c) for c in population]

        history = []
        best_ever = None
        best_ever_fitness = -1.0
        stagnant_generations = 0
        converged_at = None

        for gen in range(self.generations):
            fitnesses = [self.fitness_fn(c) for c in population]

            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_fitness = fitnesses[gen_best_idx]
            history.append(gen_best_fitness)

            if gen_best_fitness > best_ever_fitness:
                improvement = gen_best_fitness - best_ever_fitness
                best_ever_fitness = gen_best_fitness
                best_ever = population[gen_best_idx]
                if improvement < self.convergence_threshold:
                    stagnant_generations += 1
                else:
                    stagnant_generations = 0
            else:
                stagnant_generations += 1

            if best_ever_fitness >= self.target_fitness:
                converged_at = gen
                break
            if stagnant_generations >= self.convergence_patience:
                converged_at = gen
                break

            # --- elitism ---
            ranked = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
            next_population = [population[i] for i in ranked[: self.elitism_count]]

            # --- breed the rest ---
            while len(next_population) < self.population_size:
                parent_a = self._tournament_select(population, fitnesses)
                parent_b = self._tournament_select(population, fitnesses)

                if self.rng.random() < self.crossover_rate:
                    child_a, child_b = self.crossover_fn(parent_a, parent_b)
                else:
                    child_a, child_b = list(parent_a), list(parent_b)

                child_a = self.mutate_fn(child_a, self.mutation_rate)
                child_b = self.mutate_fn(child_b, self.mutation_rate)

                if self.repair_fn:
                    child_a = self.repair_fn(child_a)
                    child_b = self.repair_fn(child_b)

                next_population.append(child_a)
                if len(next_population) < self.population_size:
                    next_population.append(child_b)

            population = next_population

        final_fitnesses = [self.fitness_fn(c) for c in population]
        avg_fitness = sum(final_fitnesses) / len(final_fitnesses)
        worst_fitness = min(final_fitnesses)

        return GAResult(
            best_chromosome=best_ever if best_ever is not None else population[0],
            best_fitness=best_ever_fitness,
            avg_fitness=avg_fitness,
            worst_fitness=worst_fitness,
            generations_run=(converged_at + 1) if converged_at is not None else self.generations,
            converged_at=converged_at,
            history=history,
        )
