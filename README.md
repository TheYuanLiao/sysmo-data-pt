# Agents of SySMo model
SySMo stands for Synthetic Sweden Mobility Model (1, 2), which creates a synthetic population, a simplified microscopic representation of an actual population in Sweden. 
Statistically representative of the population, it offers crucial data for simulation models, notably agent-based models, in fields like transportation, land use, economics, and epidemiology.

1. [Documentation of SySMo](https://research.chalmers.se/publication/531094).

2. Tozluoğlu, Çağlar, Swapnil Dhamal, Sonia Yeh, Frances Sprei, Yuan Liao, Madhav Marathe, Christopher L. Barrett, and Devdatt Dubhashi. "A synthetic population of Sweden: datasets of agents, households, and activity-travel patterns." Data in Brief 48 (2023): 109209.
[Link](https://www.sciencedirect.com/science/article/pii/S2352340923003281?via%3Dihub)

## Project scope
The project delivers a synthetic replica of **Swedish travelers** (i.e., agents travel by car, walk, bike, or public transit), 
their household characteristics, activity-travel plans, and detailed traveling along the road network on an average weekday.
This repository documents the methodology of generating these data which can be further used in mobility patterns analysis, agent-based simulations, 
and studying the impact of electrification of private car fleets in Sweden.

## Steps

| Step | Script/Procedure                                  | Objective                                                                                                         |
|------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| 1    | `src\1-data-preparation.ipynb`                    | Prepare data for simulating car agents' movement in MATSim. This step uses functions in `lib\workers.py`.         |
|      | MATSim simulation*                                | All agents, 10% at a time, are simulated simultaneously in Sweden.                                                |
| 2    | `src\2-activity-plans-merging.py`                 | Merge original SySMo's plans and MATSim simulations' experienced plans, organized for further processing.         |
| 3    | `src\3-plans-description-events-processing.ipynb` | Visualize individual plans and events, i.e., driving trajectories on the road network.                            |
| 4    | `src\4-agents-filtering.ipynb`                    | Prepare agents' sociodemographic attributes with feasibility label and plans and events only for feasible agents. |
| 5    | `src\5-data-product-description.ipynb`            | A simple overview of the four main data products.                                                                 |

*We input the agents' daily activity plans along with the road network into MATSim for iterative replanning, 
aiming for a convergence on optimal activity plans for all agents. 
Subsequently, we retrieve the individual mobility trajectories of agents from the MATSim simulation.
The setup adheres to the MATSim 13.0 benchmark scenario (`src\config.xml`), with slight adjustments. 
The strategy for replanning integrates BestScore (60%), TimeAllocationMutator (30%), and ReRoute (10%)—
the percentages denote the proportion of agents utilizing these strategies.

## Data products
For plans and events, the agents are randomly divided into 10 batches.

| # | Dataset              | File                  | Description                                                                                            |
|---|----------------------|-----------------------|--------------------------------------------------------------------------------------------------------|
| 1 | Synthetic car agents | `syn_pop_all.parquet` | Contains all car agents and their attributes.                                                          |
| 2 | Activity plans       | `plans_i.parquet`     | Contains the agents' daily activity plan for an average weekday.                                       |
| 3 | Driving trajectories | `events_i.parquet`    | Agents' moving along the road network at the second level, including public transit cars' trajectories. |
| 4 | Road network         | `netowrk.shp`         | Road network.                                  |