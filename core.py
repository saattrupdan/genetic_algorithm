import numpy as np
from functools import reduce
import sys
import os

# Plots
import matplotlib.pyplot as plt

# Progress bar
from tqdm import tqdm, trange

# Parallelising fitness
from multiprocessing import Pool

# Used to suppress console output
from contextlib import contextmanager
@contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:  
            yield
        finally:
            sys.stdout = old_stdout


class Genus():

    def __init__(self, genomes: dict):
        self.genomes = genomes

    def create_organisms(self, amount: int = 1):
        ''' Create organisms of this genus. '''
        amount_range = trange(amount)
        amount_range.set_description("Creating organisms...")
        organisms = [Organism(genus = self, genome =
            {key : np.random.choice(self.genomes[key])
            for key in self.genomes.keys()}) for i in amount_range]
        return np.array(organisms)

    def create_genus(self, add = None, remove = None):
        ''' Create copy of this genus with possible modifications. '''
        genomes = np.append(np.array([param for param in self.genomes
                     if param.key not in remove]), add)
        return Genus(genomes)

class Organism():

    def __init__(self, genus: Genus, genome: dict):
        if not genus.genomes.keys() == genome.keys():
            raise TypeError('Genus keys do not match input keys.')

        self.genus = genus
        self.genome = genome
        self.fitness = None

    def breed(self, other):
        ''' Breed with another organism, creating a new organism of
            the same genus. '''

        if not self.genus == other.genus:
            raise TypeError('The two organisms are not of the same genus.')

        # Child will inherit genes from its parents randomly
        child_genome = {
            key : np.random.choice([self.genome[key], other.genome[key]])
                  for key in self.genome.keys()
            }
        return Organism(self.genus, child_genome)

    def mutate(self):
        ''' Mutate the organism by changing the value of a random gene. '''
        keys = np.array([*self.genus.genomes])
        random_key = np.random.choice(keys)
        random_val = np.random.choice(self.genus.genomes[random_key])
        self.genome[random_key] = random_val
        self.fitness = None
        return self

class Population():

    def __init__(self, genus: Genus, size: int, fitness_fn):
        self.genus = genus
        self.size = size
        self.population = genus.create_organisms(size)
        self.fittest = None

        # Fitness function cannot be a lambda expression
        self.fitness_fn = fitness_fn

    def get_fit_organisms(self, amount: int = 1):
        ''' Sample a fixed amount of organisms from the population,
            where the fitter an organism is, the more it's likely
            to be chosen. 
    
        INPUT
            (int) amount: number of fit organisms to output

        OUTPUT
            (ndarray) fit subset of population
        '''

        # Get array of organisms in population with no fitness recorded
        pop_no_fit = np.asarray([org for org in self.population
                                 if not org.fitness])

        # Compute fitness values in parallel
        with Pool() as pool:
            orgs_fitnesses = tqdm(zip(pop_no_fit, pool.imap(self.fitness_fn,
                pop_no_fit)), total = pop_no_fit.size)
            orgs_fitnesses.set_description("Computing fitness...")
            with suppress_stdout():
                for (org, new_fitness) in orgs_fitnesses:
                    org.fitness = new_fitness

        fitnesses = np.asarray([org.fitness for org in self.population])
        
        # Convert fitness values into probabilities
        probs = np.divide(fitnesses, sum(fitnesses))

        # Sort the probabilities in descending order and sort the
        # population and fitnesses in the same way
        sorted_idx = np.argsort(probs)[::-1]
        probs = probs[sorted_idx]
        self.population = self.population[sorted_idx]

        # Save the fittest genome with its fitness value
        self.fittest = {
            'genome'    : self.population[0].genome,
            'fitness'   : fitnesses[sorted_idx[0]]
            }
       
        # Get random numbers between 0 and 1 
        indices = np.random.rand(amount)
        amount_range = trange(amount)
        amount_range.set_description("Choosing fittest organisms...")
        for i in amount_range:
            # Find the index of the fitness value whose accumulated
            # sum exceeds the value of the i'th random number.
            fn = lambda x, y: (x[0], x[1] + y[1]) \
                              if x[1] + y[1] > indices[i] \
                              else (x[0] + y[0], x[1] + y[1])
            (idx, _) = reduce(fn, map(lambda x: (1, x), probs))
            indices[i] = idx - 1

        # Return the organisms indexed at the indices found above
        return self.population[indices.astype(int)]

    def evolve(self, generations: int = 1, keep: float = 0.20,
        mutate: float = 0.50):
        ''' Evolve the population.

        INPUTS
            (int) generations: number of generations to evolve
            (float) keep: percentage of population to keep each gen
            (float) mutate: percentage of population to mutate each gen
        '''
    
        print("Population evolving...")

        history = History()
        for generation in trange(generations):
            # Keep the fittest organisms of the population
            keep_amount = max(2, np.ceil(self.size * keep).astype(int))
            self.population = self.get_fit_organisms(keep_amount)
       
            # Breed until we reach the same size
            remaining = trange(self.size - keep_amount)
            remaining.set_description("Breeding...")
            for i in remaining:
                parents = np.random.choice(self.population, 2)
                child = parents[0].breed(parents[1])
                
                # Mutate child
                if np.random.rand() < mutate: child.mutate()
                
                # Add child to population
                self.population = np.append(self.population, child)

            # Store fittest genome for this generation
            history.add_entry(*self.fittest.values())

        # Print another line as there are two progress bars
        print("")

        return history

class History():

    def __init__(self):
        self.genomes = []
        self.fitnesses = []
        self.fittest = {'genome' : None, 'fitness' : None}
    
    def add_entry(self, genome, fitness):
        self.genomes.append(genome)
        self.fitnesses.append(fitness)
        self.fittest = {
            'genome' : self.genomes[np.argmax(self.fitnesses)],
            'fitness' : max(self.fitnesses)
            }
        return self

    def plot(self, save_fig = None, title = 'Fitness by generation'):
        plt.style.use("ggplot")
        plt.figure()
        plt.plot(self.fitnesses, label = "fitness")
        plt.title("Fitness by generation")
        plt.xlabel("Generations")
        plt.ylabel("Fitness")
        if save_fig:
            plt.save_fig(save_fig)
        plt.show()
        return self


if __name__ == '__main__':

    Number = Genus({'x' : range(1, 10000), 'y' : range(1, 10000)})
    def fitness_fn(number):
        return number.genome['x'] / number.genome['y']

    numbers = Population(genus = Number, size = 10000, fitness_fn = fitness_fn)
    history = numbers.evolve(generations = 5)

    print(f"Fittest genome across all generations:")
    print(history.fittest)
    history.plot()
