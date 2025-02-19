import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F

class EncoderRNN(nn.Module):
    def __init__(self, hidden_size, embedding, n_layers=1, dropout=0):
        super(EncoderRNN, self).__init__()
        self.n_layers = n_layers
        self.hidden_size = hidden_size
        self.embedding = embedding

        # Initialize GRU; the input_size and hidden_size params are both set to 'hidden_size'
        #   because our input size is a word embedding with number of features == hidden_size
        self.gru = nn.GRU(hidden_size, hidden_size, n_layers,
                          dropout=(0 if n_layers == 1 else dropout))

    def forward(self, input_seq, hidden=None):
        
        input_seq = input_seq.transpose(0,1)
        
        x = self.embedding(input_seq)
        
        outputs, hidden = self.gru(x)
        return outputs,hidden

    
class DecoderRNN(nn.Module):
    def __init__(self,embedding,hidden_size,output_size,n_layers,dropout):
        super(DecoderRNN, self).__init__()
        self.embedding = embedding
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.n_layers = n_layers
        self.dropout = dropout
        self.gru = nn.GRU(hidden_size, hidden_size, n_layers, dropout=(0 if n_layers == 1 else dropout))
        self.mlp = nn.Linear(2*hidden_size,hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        
    def forward(self,input_seq,last_hidden,encoder_outputs):
        #print(last_hidden.shape)
        input_seq = input_seq.transpose(0,1)
        embedding = self.embedding(input_seq)
        #print(embedding.shape)
        #embedding = embedding.transpose(0,1)
        #print(embedding.shape)

        outputs, hidden = self.gru(embedding,last_hidden)
        context = torch.mean(encoder_outputs, dim = 0)
        #print(context.shape)
        outputs = outputs.squeeze()
        # print(encode_info.shape)
        #print(outputs.shape)
        # exit()
        concat_input = torch.cat((outputs, context), 1)
        concat_output = torch.tanh(self.mlp(concat_input))
        output = self.out(concat_output)
        output = F.softmax(output, dim=1)
        # print(output.shape)
        # print(hidden.shape)
        # exit()
        return output,hidden

class AttnDecoderRNN(nn.Module):
    def __init__(self,embedding,hidden_size,output_size,n_layers,dropout):
        super(AttnDecoderRNN, self).__init__()
        self.embedding = embedding
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.n_layers = n_layers
        self.dropout = dropout
        self.gru = nn.GRU(hidden_size, hidden_size, n_layers, dropout=(0 if n_layers == 1 else dropout))
    
        self.mlp = nn.Linear(2*hidden_size,hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        
    def forward(self,input_seq,last_hidden,encoder_outputs):
        #print(last_hidden.shape)
        input_seq = input_seq.transpose(0,1)
        embedding = self.embedding(input_seq)
        #print(embedding.shape)
        #embedding = embedding.transpose(0,1)
        #print(embedding.shape)
        
        outputs, hidden = self.gru(embedding,last_hidden)
        attn_weights = torch.sum(outputs * encoder_outputs, dim=2)
        attn_weights = attn_weights.t()
        attn_weights = F.softmax(attn_weights, dim=1).unsqueeze(1)
        #print(attn_weights.shape)
        context = attn_weights.bmm(encoder_outputs.transpose(0, 1))
        context = context.squeeze(1)
        #print(encoder_outputs.shape)

        outputs = outputs.squeeze()

        # print(encode_info.shape)
        #print(outputs.shape)
        # exit()
        concat_input = torch.cat((outputs, context), 1)
        concat_output = torch.tanh(self.mlp(concat_input))
        output = self.out(concat_output)
        output = F.softmax(output, dim=1)
        # print(output.shape)
        # print(hidden.shape)
        # exit()
        return output,hidden

# import torch
# import torch.nn as nn
# from torch import optim
# import torch.nn.functional as F

# class EncoderRNN(nn.Module):
#     def __init__(self, hidden_size, embedding, n_layers=1, dropout=0):
#         super(EncoderRNN, self).__init__()
#         self.n_layers = n_layers
#         self.hidden_size = hidden_size
#         self.embedding = embedding

#         # Initialize GRU; the input_size and hidden_size params are both set to 'hidden_size'
#         #   because our input size is a word embedding with number of features == hidden_size
#         self.gru = nn.GRU(hidden_size, hidden_size, n_layers,
#                           dropout=(0 if n_layers == 1 else dropout), bidirectional=True)

#     def forward(self, input_seq, input_lengths, hidden=None):
#         # Convert word indexes to embeddings
#         embedded = self.embedding(input_seq)
#         # Pack padded batch of sequences for RNN module
#         input_lengths = input_lengths.cpu()
#         packed = torch.nn.utils.rnn.pack_padded_sequence(embedded, input_lengths)
#         # Forward pass through GRU
#         outputs, hidden = self.gru(packed, hidden)
#         # Unpack padding
#         outputs, _ = torch.nn.utils.rnn.pad_packed_sequence(outputs)
#         # Sum bidirectional GRU outputs
#         outputs = outputs[:, :, :self.hidden_size] + outputs[:, : ,self.hidden_size:]
#         # Return output and final hidden state
#         return outputs, hidden
# # Luong attention layer
# class Attn(torch.nn.Module):
#     def __init__(self, method, hidden_size):
#         super(Attn, self).__init__()
#         self.method = method
#         if self.method not in ['dot', 'general', 'concat']:
#             raise ValueError(self.method, "is not an appropriate attention method.")
#         self.hidden_size = hidden_size
#         if self.method == 'general':
#             self.attn = torch.nn.Linear(self.hidden_size, hidden_size)
#         elif self.method == 'concat':
#             self.attn = torch.nn.Linear(self.hidden_size * 2, hidden_size)
#             self.v = torch.nn.Parameter(torch.FloatTensor(hidden_size))

#     def dot_score(self, hidden, encoder_output):
#         return torch.sum(hidden * encoder_output, dim=2)

#     def general_score(self, hidden, encoder_output):
#         energy = self.attn(encoder_output)
#         return torch.sum(hidden * energy, dim=2)

#     def concat_score(self, hidden, encoder_output):
#         energy = self.attn(torch.cat((hidden.expand(encoder_output.size(0), -1, -1), encoder_output), 2)).tanh()
#         return torch.sum(self.v * energy, dim=2)

#     def forward(self, hidden, encoder_outputs):
#         # Calculate the attention weights (energies) based on the given method
#         if self.method == 'general':
#             attn_energies = self.general_score(hidden, encoder_outputs)
#         elif self.method == 'concat':
#             attn_energies = self.concat_score(hidden, encoder_outputs)
#         elif self.method == 'dot':
#             attn_energies = self.dot_score(hidden, encoder_outputs)

#         # Transpose max_length and batch_size dimensions
#         attn_energies = attn_energies.t()

#         # Return the softmax normalized probability scores (with added dimension)
#         return F.softmax(attn_energies, dim=1).unsqueeze(1)

# class LuongAttnDecoderRNN(nn.Module):
#     def __init__(self, attn_model, embedding, hidden_size, output_size, n_layers=1, dropout=0.1):
#         super(LuongAttnDecoderRNN, self).__init__()

#         # Keep for reference
#         self.attn_model = attn_model
#         self.hidden_size = hidden_size
#         self.output_size = output_size
#         self.n_layers = n_layers
#         self.dropout = dropout

#         # Define layers
#         self.embedding = embedding
#         self.embedding_dropout = nn.Dropout(dropout)
#         self.gru = nn.GRU(hidden_size, hidden_size, n_layers, dropout=(0 if n_layers == 1 else dropout))
#         self.concat = nn.Linear(hidden_size * 2, hidden_size)
#         self.out = nn.Linear(hidden_size, output_size)

#         self.attn = Attn(attn_model, hidden_size)

#     def forward(self, input_step, last_hidden, encoder_outputs):
#         # Note: we run this one step (word) at a time
#         # Get embedding of current input word
#         embedded = self.embedding(input_step)
#         embedded = self.embedding_dropout(embedded)
#         # Forward through unidirectional GRU
#         # print(embedded.shape)
#         # print(last_hidden.shape)
#         # exit()
#         rnn_output, hidden = self.gru(embedded, last_hidden)
#         # Calculate attention weights from the current GRU output
#         attn_weights = self.attn(rnn_output, encoder_outputs)
#         # Multiply attention weights to encoder outputs to get new "weighted sum" context vector
#         context = attn_weights.bmm(encoder_outputs.transpose(0, 1))
#         # Concatenate weighted context vector and GRU output using Luong eq. 5
#         rnn_output = rnn_output.squeeze(0)
#         context = context.squeeze(1)
#         concat_input = torch.cat((rnn_output, context), 1)
#         concat_output = torch.tanh(self.concat(concat_input))
#         # Predict next word using Luong eq. 6
#         output = self.out(concat_output)
#         output = F.softmax(output, dim=1)
#         # Return output and final hidden state
#         return output, hidden

























