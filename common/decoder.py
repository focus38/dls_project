# Декодер
from torchnlp.encoders import LabelEncoder
from torchaudio.models.decoder import ctc_decoder

class CTCDecoder():
    def __init__(self, characters):
        """
        characters: массив символов, которые должны декодировать
        """
        self.blank_token = '-'
        self.sil_token = ' '
        self.characters = characters.copy()
        self.encoder = LabelEncoder(self.characters, reserved_labels=[self.blank_token], unknown_index=0)
        self.decoder = ctc_decoder(tokens=self.encoder.index_to_token,
                                   lexicon=None, nbest=1, beam_size=200,
                                   blank_token=self.blank_token,
                                   sil_token=self.sil_token)
    
    def decode(self, logits): # Тут на входе logits из модели в размере T, B, N
        decoder_input = logits.permute(1, 0, 2).detach().cpu() # B, T, N
        decoder_input = decoder_input.contiguous()
        beam_search_result = self.decoder(decoder_input)
        result = []
        if beam_search_result == None or len(beam_search_result) == 0:
            return result

        batch_size = decoder_input.shape[0]
        for num_batch in range(batch_size):
            beam_search_item = beam_search_result[num_batch]
            text_items = [''.join(self.encoder.batch_decode(z.tokens)).strip() for z in beam_search_item]
            text_items = [t for t in text_items if t != '' and t != '-']
            text = ''.join(text_items)
            text = text.replace(' ','').replace(',','.')
            result.append(text)
        return result
