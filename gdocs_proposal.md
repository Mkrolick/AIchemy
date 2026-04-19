Chemy Proposal V5
Introduction:

Most chemical synthesis pathway planning is designed around the problem: “Given a target molecule, what is the cheapest way to produce it”. The above problem was dissected more deeply through Sparrow by the Corley Group using retrosythesis encoded in an MILP formulation. I want to ask a different question: "Given material market prices, what should I make to maximize profit margins using chemo-enzymatic reactions?" 

This changes the problem a few ways: The target product is no longer fixed; it is a decision variable from which the solver should operate on. The objective shifts to cost minimization from to profit maximization. Lastly, the reaction network expands to include chemo-enzymatic reactions. That is to say, that the goal of this is to generate a sub graph such that the inputs or the cost of the inputs minus the cost of the outputs is maximized under yield and reaction uncertainty.

Joint product and route selection is not itself new. There is a history of work that has done this. The work that I present here expands this specific joint product in route selection to that of margin optimization in the chemo-enzymatic space using MILP formulation).

Important scope caveat: this is a core screening heuristic, not a production planning tool. This does not include capital costs, regulatory compliance, or process development. It should not be treated or approached as such.
Database Preparation:
We note that merging enzymatic and chemical reactions is a known and non-trivial difficulty. Specifically, many databases, even those that rely on the same format, use different conventions for storing atomic information (excluding H2O, excluding cofactors, yield rates, etc..). We also note additionally many chemical databases are and remain highly paywalled (5k+). For this reason we stick to open source databases using MetaNetX (Metabolic and Biochemical Reaction Database) and USPTO (Chemical Reaction Database).

For this reason we follow the precedent set by minChemBio:
Reaction Deduplication - Done through using SMILES string matching and then by Tanimoto similarity coefficients between reactants and products reduce the set. 
Molecule deduplication - Relabeling molecules to their MetaNetX identifier if there is a dual match by exact structural matches (Done with Tanimoto = 1.0)
Non-Hydrocarbon removal - Remove all reactions with less than or equal to 1 carbon count among reactants or products (restriction to synthesis relevant transformations)
Additionally, there are many parameters that are required for the constraints that we will use within the MIPS formulation. These include: 
Price - I can use existing ChemPrize software to generate the prices of a specific chemical at a single gram cost.
Stoichiometric Coefficients - For this, within MetaNetX, this is defined. For USPTO, that will require using SYN-RBL and then only retaining successfully balanced reactions.
Yield Data - MetaNetX does not include yield data; however, commonly cited numbers are within 0.85 to 0.95. USPTO includes partial usage of yield number (~15%). In the worst case, mean yields can be used as a substitute for reactions that do not include yields.
Delta G - We ask the question of if the reaction is feasible from a thermodynamic context. For MetaNetX, we use directionality observed within the reactions and assume that they are only in the forward direction, as a result of that being experimentally validated. Note for the USPTO reactions, there is no need for delta G as they are forwards only 🥳!

Problem Formulation:

We approach this problem by defining a hypergraph over chemicals with edges that are represented by reactions. We aim to maximize expected reward from the selling in two scenarios from produced chemicals exclusively or from the combination of produced chemicals and some feedstock.

Sets and Parameters:
Symbol
Definition
R = E ∪ S
Set of reactions: enzymatic (E) and chemical (S)
C
All chemicals
πₘ
Catalog-scale market price of chemical c (single consistent scale)
aₘ,ᵣ, ηᵣ
Stoichiometric coefficient and expected yield for reaction r
κᵣ, φᵣ
Variable operating cost and fixed activation cost for reaction r (possible)
ΔG’°ᵣ
Standard transformed Gibbs energy of reaction r (not using left for historical reasons)
B
Total budget constraint


Decision variables.
Variable
Domain
Meaning
yᵣ
{0, 1}
Whether reaction r is activated
wₘ
{0, 1}
Whether product m is targeted for sale
I
{0, 1}
Whether a product is an intermediate or not
fᵣ
≥ 0
Molar flow through reaction r
qᵇᵘʸ, qˢᵉˡˡ
≥ 0
Quantities purchased and sold


Constraints: 
Mass balance over product c:

We note existing work on similar problems finding thermodynamically favorable pathways in chemical reactions. More specifically, Pal, et al’s work (https://arxiv.org/html/2411.15900) defines a constraint for mass balance. We extend the above notion to include input prices which we then define the constraint as:



(From obsidian notes, I can’t figure out how to render in google)

The formula above denotes that for every chemical c, the sum of the mass produced (haha yeilded) and bought is equal to the amount consumed in reactions or sold. We note that the values of q will be determined by the associated w decision variable.
Preventing invisible activations (lower bound): 

Flow must be at least at least above a minimal constant.
Enforcing flow activations (upper bound): 

Where the max flow can be defined as the B / sum(inputs of R_r). In the case products are not defined, let input R_r have price pi_m where pi_m is median price.

Purchased goods are less than or equal to total cost:


For each product bought bought, the sum of product quantity * price is less than B, the total budget.
Purchased goods are less than or equal to total cost:
Basic constraints binding I, wₘ to qᵇᵘʸ, qˢᵉˡˡ.
Solver: 
Use Gurobi for solver.






Todos / thinking about:
Fixed costs of reactions (equipment)
Thinking about it. 
Would require a form of webscraper over patent filings (Extract)
Should be scopeable in a week. 
Set up a similar scrapper in one night with multi agent debates in 1 night
Scraper could also yield better data on the stoichiometry coefficient as opposed to generation from chemical structure. 
Sell a restricted quantity of final products
Simple restriction where Sum(wₘ)  < N where N is num of sellable products
Transition costs between enzymatic and chemical reactions











—--


Is this any different technically?  Profit = price - cost. I'd imagine that both price and cost are linear functions of quantities of chemicals, in which case profit is a linear function too?
Absolutely, agree that profit is linear.
The reaction space is not bounded by a single product to produce. It is different in the encoding in the sense that each chemical is a possible product.
Is your point here that you have to pay for the enzymes, but you can reuse them (they are both inputs and outputs)?
The intended point is that I am adding enzyme mediated transformations that is not included in synthesis space for route selection.
Enzymes are catalysts so in reactions they are typically not consumed. However, they become deactivated with use. They would enter the reaction as an amortized cost.
Where does the uncertainty come from?
Some yields in patent data tend to be volatile because operating conditions vary across sources and reporting standards are inconsistent.
Ideally from ASKCOS running on AWS which can predict the likelihood of the reaction proceeding.
What are your integer vars?
Defined below.
Are there also reactions whose existence and properties you can derive from first principles, rather than by looking them up in a database of experimentally validated reactions?
There are a few platforms for running quantum chemistry simulations however they are very computationally expensive and when they work then tend to only give activation energies rather than yield. There are some approximate methods in the machine learning space and those are less expensive but still computationally expensive without cluster access.
Another possibility is that once you and others rush to manufacture the chemical with the highest profit margin, its market price comes down through competition, and now you have to rerun the solver with the new price?  (Then possibly market effects should be considered at the start, particularly if introducing new products isn't free - there will generally be startup costs related to manufacturing, regulatory compliance, and marketing, although you explicitly excluded some of those above.)
Absolutely agreed. I would like to add the cost of chemical manufacturing and licence compliance to the model as well.
standard flow constraint, just on hypergraphs (but any hypergraph can be converted to a standard graph by introducing a new node for each hyperedge, I think)
Yep. With just yield coefficients.
Flow must be at least at least above a minimal constant.
In a real world setting running a reaction for products of minimal yield would be incredibly inefficient. Especially if it is not the main product being manufactured. This is in a sense a cut off point for that.
This is fine, but your writeup should discuss the computational difficulty of the problem.  It's probably an LP problem (thus, not NP-hard -- was the Corley Group's problem NP-hard since they used MILP? why the discrepancy?).  Can your problem be reduced to an even more specialized known problem such as lightest path in a hypergraph?  I suggest looking at this classic paper on hypergraph
They used a non-linear objective function aiming to optimize over the joint products and can't as a result use an LP. They also use binary decision variables.
I think an LP is a good place to start if you exclude fixed costs and cardinality constraints. Otherwise, an MILP would be preferable to add that in.
I think that and hope to show the problem (at least in the most reduced LP form) can be reduced to the lightest path in a hypergraph. Thank you for attaching the paper.
Is it fair to say that getting the data is the hard part in this project, and the reduction is pretty straightforward?
The data part is currently non-trivial. Possibly, there are unknown unknowns.
