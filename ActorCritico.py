
import torch 
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import Gym
from collections import OrderedDict
import matplotlib.pyplot as plt
from matplotlib import gridspec
import time



class actorCriticNet(nn.Module):
    def __init__(self, n_hidden_layers=4, n_hidden_nodes=32,
                 learning_rate=0.01, bias=False, device='cpu'):
        super(actorCriticNet, self).__init__()
        
        self.device = device
        self.n_inputs = 12
        self.n_outputs = 256
        self.n_hidden_nodes = n_hidden_nodes
        self.n_hidden_layers = n_hidden_layers
        self.learning_rate = learning_rate
        self.bias = bias
        self.action_space = np.arange(256)

        
        # Generate network according to hidden layer and node settings
        self.layers = OrderedDict()
        self.n_layers = 2 * self.n_hidden_layers
        for i in range(self.n_layers + 1):
            # Define single linear layer
            if self.n_hidden_layers == 0:
                self.layers[str(i)] = nn.Linear(
                    self.n_inputs,
                    self.n_outputs,
                    bias=self.bias)
            # Define input layer for multi-layer network
            elif i % 2 == 0 and i == 0 and self.n_hidden_layers != 0:
                self.layers[str(i)] = nn.Linear( 
                    self.n_inputs, 
                    self.n_hidden_nodes,
                    bias=self.bias)
            # Define intermediate hidden layers
            elif i % 2 == 0 and i != 0:
                self.layers[str(i)] = nn.Linear(
                    self.n_hidden_nodes,
                    self.n_hidden_nodes,
                    bias=self.bias)
            else:
                self.layers[str(i)] = nn.ReLU()
                
        self.body = nn.Sequential(self.layers)
            
        # Define policy head
        self.policy = nn.Sequential(
            nn.Linear(self.n_hidden_nodes,
                      self.n_hidden_nodes,
                      bias=self.bias),
            nn.ReLU(),
            nn.Linear(self.n_hidden_nodes,
                      self.n_outputs,
                      bias=self.bias))
        # Define value head
        self.value = nn.Sequential(
            nn.Linear(self.n_hidden_nodes,
                      self.n_hidden_nodes,
                      bias=self.bias),
            nn.ReLU(),
            nn.Linear(self.n_hidden_nodes,
                      1, 
                      bias=self.bias))

        self.optimizer = torch.optim.Adam(self.parameters(),
                                          lr=self.learning_rate)

    def predict(self, state):
        body_output = self.get_body_output(state)
        probs = F.softmax(self.policy(body_output), dim=-1)
        return probs, self.value(body_output)

    def get_body_output(self, state):
        state_t = torch.FloatTensor(state).to(device=self.device)
        return self.body(state_t)
    
    def get_action(self, state):
        probs = self.predict(state)[0].detach().numpy()
        action = np.random.choice(self.action_space, p=probs)
        return action
    
    def get_log_probs(self, state):
        body_output = self.get_body_output(state)
        logprobs = F.log_softmax(self.policy(body_output), dim=-1)
        return logprobs    



class A2C():
    def __init__(self, env, network):
        
        self.env = env
        self.network = network
        self.action_space = np.arange(12)
        
    def generate_episode(self):
        states, actions, rewards, dones, next_states = [], [], [], [], []
        done = False
        while done == False:
            action = self.network.get_action(self.s_0)
            s_1, r, done = self.env.step(action)
            self.reward += r
            states.append(self.s_0)
            next_states.append(s_1)
            actions.append(action)
            rewards.append(r)
            dones.append(done)
            self.s_0 = s_1
            
            if done:
                self.ep_rewards.append(self.reward)
                self.s_0 = self.env.reset()
                self.reward = 0
                self.ep_counter += 1
                if self.ep_counter >= self.num_episodes:
                    break            

        return states, actions, rewards, dones, next_states
    
    def calc_rewards(self, batch):
        states, actions, rewards, dones, next_states = batch
        rewards = np.array(rewards)
        total_steps = len(rewards)
        
        state_values = self.network.predict(states)[1]
        next_state_values = self.network.predict(next_states)[1]
        done_mask = torch.ByteTensor(dones).to(self.network.device)
        next_state_values[done_mask] = 0.0
        state_values = state_values.detach().numpy().flatten()
        next_state_values = next_state_values.detach().numpy().flatten()
        
        G = np.zeros_like(rewards, dtype=np.float32)
        td_delta = np.zeros_like(rewards, dtype=np.float32)
        dones = np.array(dones)
        
        for t in range(total_steps):

            last_step = min(self.n_steps, total_steps - t)
            
            # Look for end of episode
            check_episode_completion = dones[t:t+last_step]
            if check_episode_completion.size > 0:
                if True in check_episode_completion:
                    next_ep_completion = np.where(check_episode_completion == True)[0][0]
                    last_step = next_ep_completion
            
            # Sum and discount rewards
            G[t] = sum([rewards[t+n:t+n+1] * self.gamma ** n for 
                        n in range(last_step)])
        
        if total_steps > self.n_steps:
            G[:total_steps - self.n_steps] += next_state_values[self.n_steps:] \
                * self.gamma ** self.n_steps
        td_delta = G - state_values
        return G, td_delta
        
    def train(self, n_steps=5, num_episodes=2000, gamma=0.99, beta=1-3, zeta=0.5):
        self.n_steps = n_steps
        self.gamma = gamma
        self.num_episodes = num_episodes
        self.beta = beta
        self.zeta = zeta
        
        # Set up lists to log data
        self.ep_rewards = []
        self.kl_div = []
        self.policy_loss = []
        self.value_loss = []
        self.entropy_loss = []
        self.total_policy_loss = []
        self.total_loss = []
        
        self.s_0 = self.env.reset()
        self.reward = 0
        self.ep_counter = 0
        while self.ep_counter < num_episodes:

            ready = self.env.ready()
            while ready == False:
                ready = self.env.ready()
                time.sleep(0.5)
            
            batch = self.generate_episode()
            G, td_delta = self.calc_rewards(batch)
            states = batch[0]
            actions = batch[1]
            current_probs = self.network.predict(states)[0].detach().numpy()
            
            self.update(states, actions, G, td_delta)
            
            new_probs = self.network.predict(states)[0].detach().numpy()
            kl = -np.sum(current_probs * np.log(new_probs / current_probs))                
            self.kl_div.append(kl)
            
            #print("\rMean Rewards: {:.2f} Episode: {:d}    ".format(
            #    np.mean(self.ep_rewards[-100:]), self.ep_counter), end="")
            
            
    def plot_results(self):
        avg_rewards = [np.mean(self.ep_rewards[i:i + self.batch_size]) 
                       if i > self.batch_size 
            else np.mean(self.ep_rewards[:i + 1]) for i in range(len(self.ep_rewards))]

        plt.figure(figsize=(15,10))
        gs = gridspec.GridSpec(3, 2)
        ax0 = plt.subplot(gs[0,:])
        ax0.plot(self.ep_rewards)
        ax0.plot(avg_rewards)
        ax0.set_xlabel('Episode')
        plt.title('Rewards')

        ax1 = plt.subplot(gs[1, 0])
        ax1.plot(self.policy_loss)
        plt.title('Policy Loss')
        plt.xlabel('Update Number')

        ax2 = plt.subplot(gs[1, 1])
        ax2.plot(self.entropy_loss)
        plt.title('Entropy Loss')
        plt.xlabel('Update Number')

        ax3 = plt.subplot(gs[2, 0])
        ax3.plot(self.value_loss)
        plt.title('Value Loss')
        plt.xlabel('Update Number')

        ax4 = plt.subplot(gs[2, 1])
        ax4.plot(self.kl_div)
        plt.title('KL Divergence')
        plt.xlabel('Update Number')

        plt.tight_layout()
        plt.show()
        
    def calc_loss(self, states, actions, rewards, advantages, beta=0.001):
        actions_t = torch.LongTensor(actions).to(self.network.device)
        rewards_t = torch.FloatTensor(rewards).to(self.network.device)
        advantages_t = torch.FloatTensor(advantages).to(self.network.device)
        
        log_probs = self.network.get_log_probs(states)
        log_prob_actions = advantages_t * log_probs[range(len(actions)), actions]
        policy_loss = -log_prob_actions.mean()
        
        action_probs, values = self.network.predict(states)
        entropy_loss = -self.beta * (action_probs * log_probs).sum(dim=1).mean()
        
        value_loss = self.zeta * nn.MSELoss()(values.squeeze(-1), rewards_t)
        
        # Append values
        self.policy_loss.append(policy_loss)
        self.value_loss.append(value_loss)
        self.entropy_loss.append(entropy_loss)
        
        return policy_loss, entropy_loss, value_loss
        
    def update(self, states, actions, rewards, advantages):
        self.network.optimizer.zero_grad()
        policy_loss, entropy_loss, value_loss = self.calc_loss(states, 
            actions, rewards, advantages)
        
        total_policy_loss = policy_loss - entropy_loss
        self.total_policy_loss.append(total_policy_loss)
        total_policy_loss.backward(retain_graph=True)
        
        value_loss.backward()
        
        total_loss = policy_loss + value_loss + entropy_loss
        self.total_loss.append(total_loss)
        self.network.optimizer.step()






env = Gym.robot()
net = actorCriticNet(learning_rate=1e-3, n_hidden_layers=4, n_hidden_nodes=64)
a2c = A2C(env, net)
a2c.train(n_steps=50 , num_episodes=2000, beta=1e-3, zeta=1e-3)  
a2c.plot_results()