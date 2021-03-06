from hashlib import sha256
from merklelib import MerkleTree
from blake3 import blake3

import time
import math
import json
import ecdsa
import codecs
import cryptocode
import base58
import zlib, base64

password = ""


##############################################################################

#Init for security
def inputPassword(new):
    global password
    password = new 

def compressAddress(public):
    unencoded_string = bytes.fromhex(public)
    encoded_string = base58.b58encode(unencoded_string)

    return encoded_string.decode('ISO-8859-1')

def decompressAddress(public):
    return base58.b58decode(public).hex()
##############################################################################
#Hash functions for varying usage

def stringHash(string):
    return sha256(str(string).encode('ISO-8859-1')).digest().hex()

def rawHash(string):
    return sha256(str(string).encode('ISO-8859-1')).digest()

def addHash(string1, string2):
    return stringHash(rawHash(string1) + rawHash(string2))

def SHAKE6(blockData, nonce):
    return sha256(blake3((hex(blockData + nonce)).encode()).digest()).hexdigest()

def SHAKE6VAL(blockData, nonce):
    return int.from_bytes(sha256(blake3((hex(blockData + nonce)).encode()).digest()).digest(),"big")



#generates difficulty target based off of hex target
def arbDifficulty(hashDemand):
    highest = bin((2**256)-1)
    hashDemand = int(hashDemand, 16)
    
    return bin(round((int(highest, 2))/hashDemand))

def calculateFee(transaction):
    try:
        transaction = transaction.__dict__
    except:
        pass


    return len(json.dumps(transaction).encode("ISO-8859-1").hex()) * 500


#block/transaction verification:

def verifyBlock(block, blockchain):
    try:
        block = block.__dict__
    except:
        try:
            block = json.loads(block)
        except:
            pass


    try:
        #reward starts at 100 coins, is cut in half every 100000 blocks
        block_reward = math.floor((100 * (10**9)) / (2 **(math.floor(block["height"]/100000))))


        for transaction in block["transactions"]:
            if transaction["sender"] == "0000000000000000000000000000000000000000000000000000000000000000":
                if transaction["txamount"] != block_reward:
                    return False
                elif (transaction["outputs"][0][1]) != block_reward:
                    return False

                try:
                    ecdsa.VerifyingKey.from_string(bytes.fromhex(block["miner"]), curve=ecdsa.SECP256k1,hashfunc=sha256).verify(bytes.fromhex(transaction["signed"]),bytes(transaction["txhash"] + transaction["nonce"],"ISO-8859-1"))
                except:
                    return False
            else:
                if not verifyTransaction(blockchain, transaction):
                    return False


        if blockchain.size > 10:
            refTime = blockchain.chainDict[block["height"] - 5]["timeStamp"]

            if (refTime + 5000) < block["timeStamp"] or (refTime - 5000) > block["timeStamp"]:
                return False

        #check to see if height is invalidly high
        if len(blockchain.chainDict) < block["height"]:
            return False

        #check to see if proof is valid
        if (SHAKE6(stringHash(json.dumps(block["transactions"]) + block["previousBlock"] + str(block["timeStamp"])), int(block["nonce"],16)) != block["proof"]):
            return False

        if (blockchain.chainDict[block["height"] - 1]["proof"] != block["previousBlock"]):
            return False

        if (int(block["proof"],16) > int(arbDifficulty(block["difficulty"]),2)):
            return False
    except:
        return False


    return True

        

def verifyTransaction(blockchain, transaction):
    try:
        transaction = transaction.__dict__
    except:
        pass 
    

    #generating information on sender:
    userBal = generateBalance(blockchain, transaction["sender"])
    minerFee = calculateFee(transaction)

    nonces = []
    account = transaction['sender']
    for y in blockchain.chainDict:
        for z in y["transactions"]:
            if (z["sender"] == account):
                nonces.append(z['nonce'])

    if nonces.count(transaction['nonce']) > 0:
        return False


    
    try:
        ecdsa.VerifyingKey.from_string(bytes.fromhex(transaction["sender"]),curve=ecdsa.SECP256k1, hashfunc=sha256).verify(bytes.fromhex(transaction["signed"]),bytes(transaction["txhash"] + transaction["nonce"], "ISO-8859-1"))
    except:
        return False

    #check to see if amount spent is too much
    if transaction["txamount"] > userBal:
        return False
    else:
        total = 0
        for x in transaction["outputs"]:
            total += x[1]
            
        if total > userBal:
            return False 

        if total < 1:
            return False

        if total < minerFee:
            return False

    return True

    
def nodeVerifyTransaction(transaction):
    if (verifyTransaction(transaction)):
        transaction.verifications += 1



##############################################################################
#account information grabbing
def generateBalance(blockchain, account):
    try:
        with open("knownData.dat", "w") as knownFile:
            data = json.loads(knownFile.read())

        return data["bals"][account]
    except:
        total = 0
        for x in blockchain.chainDict:
            for y in x["transactions"]:
                for z in y["outputs"]:
                    if z[0] == account:
                        total += z[1]

                if y["sender"] == account:
                    total -= y["txamount"]

        return total

            
##############################################################################
#blockchain element classes


class blockChain:
    def __init__(self):
        self.chainDict = []
        self.size = len(self.chainDict)
        self.dataSize = len(json.dumps(self.chainDict))

    def createGenesis(self, miner, hashdemand):
        self.chainDict = []
        self.genesisHashDemand = hashdemand

        genesis = block(self)
        genesis.difficulty = "{:016x}".format(hashdemand)
        genesis.complete(time.time())
        genesis.mrkl = str(MerkleTree(genesis.transactions, stringHash))[12:-2]
        genesis.tx_num = 1
        mine(genesis, miner, self)



    def addBlock(self, block):
        self.chainDict.append(block.__dict__)
        self.size += 1

    def writeToFile(self):
        try:
            data = json.dumps(self.chainDict)
            data = base64.b64encode(zlib.compress(data.encode('ISO-8859-1'),9))
            data = data.decode('ISO-8859-1')

            file = open("blockchain.dat", 'wb')
            file.write(bytes(data,"ISO-8859-1"))
            file.close()
            return True
        except:
            return False

    def retrieveFromFile(self):
        try:
            file = open("blockchain.dat", 'rb')
            data = json.loads(codecs.decode(zlib.decompress(base64.b64decode(file.read())), "ISO-8859-1"))
            file.close()

            return data
        except Exception as e:
            print("Error Retrieving data: " + str(e))
            return self.chainDict

    def decompressFile(self):
        file = open("blockchain.dat", 'rb')
        data = json.loads(codecs.decode(zlib.decompress(base64.b64decode(file.read())), "ISO-8859-1"))
        file.close()

        file = open("blockchaindecompressed.dat", 'w')
        file.write(json.dumps(data, indent=4))
        file.close()

    def syncChain(self):
        self.chainDict = self.retrieveFromFile()
        self.size = len(self.chainDict)



class block:
    def __init__(self, blockchain):
        self.height = len(blockchain.chainDict)

        if (self.height != 0):
            self.previousBlock = blockchain.chainDict[-1]["proof"] 
            self.difficulty = self.calculateDifficuty(blockchain)
        else:
            self.previousBlock = "0"
            self.difficulty = "{:016x}".format(1000)

        self.version = 0.1
        self.transactions = []
        self.nonce = 0

    def calculateDifficuty(self, blockChain):
        chain = blockChain.chainDict
        if (self.height == 0): return 
        if (self.height % 144 == 0):
            total_time = round(time.time(), 2) - chain[self.height - 144]["timeStamp"]
            
            return "{:016x}".format(round(int(chain[self.height - 1]["difficulty"],16) * ((1440 * 60)/total_time)))
        else:
            return chain[self.height - 1]["difficulty"]
    
    def addTransaction(self, blockchain, transaction):
        if verifyTransaction(blockchain, transaction) == True:
            self.transactions.append(transaction.__dict__)

    def complete(self, timestamp): 
        self.timeStamp = round(timestamp, 2)

    def addBlockToChain(self, blockchain, nonce, miner):
        #adding fees to all transactions in block

        for y, x in enumerate(self.transactions):
            try:
                self.transactions[y] = x.__dict__
            except:
                pass


        for y,x in enumerate(self.transactions):
            if (x["sender"] != "0000000000000000000000000000000000000000000000000000000000000000"):
                fee = calculateFee(self.transactions[y])

                self.transactions[y]["outputs"][0] = [self.transactions[y]["outputs"][0][0], int(self.transactions[y]["txamount"] - fee)]
                self.transactions[y]["outputs"].append([miner, int(fee)])

        #formatting for saving chain
        self.miner = miner
        self.nonce = hex(nonce)
        self.tx_num = len(self.transactions)

        #murkleTree = MerkleTree(self.transactions, stringHash)
        self.mrkl = str(MerkleTree(self.transactions, stringHash))[12:-2]
        blockchain.addBlock(self)

class transaction:
    privKey = ""
    def __init__(self, sender, reciever, amount, timestamp, privkey, nonce):
        global privKey

        privKey = privkey
        self.timestamp = round(timestamp, 2)
        self.sender = sender
        self.outputs = [[reciever, int(amount)]]
        self.txamount = int(amount)
        self.txhash = stringHash(sender + str(json.dumps(self.outputs)) + str(self.timestamp))
        self.nonce = '{:x}'.format(nonce)
        self.sign()

    def addMessage(self, message):
        self.msg = bytes(str(message), "ISO-8859-1").hex()


    def addOutput(self,output):
        self.outputs.append(output)
        self.txamount += output[1]
        self.txhash = stringHash(self.sender + str(json.dumps(self.outputs)) + str(self.timestamp))
        self.sign()
        
    def sign(self):
        global privKey
        global sender
        self.signed = ecdsa.SigningKey.from_string(bytes.fromhex(privKey),curve=ecdsa.SECP256k1, hashfunc=sha256).sign(bytes(self.txhash + self.nonce, 'ISO-8859-1')).hex()
        


class wallet: 
    def __init__(self):
        self.publicHex = ""
        self.privateHex = ""

    def generateKeys(self, password):
        global public
        global private

        private = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        public = private.get_verifying_key()
        self.publicHex = public.to_string("compressed").hex()
        privateHexUsable = private.to_string().hex()
        self.privateHex = cryptocode.encrypt(private.to_string().hex(), password)
        self.nonce = 0
        self.created = round(time.time(), 2)

        file = open("wallet.dat", 'w')
        file.write(json.dumps(self.__dict__))
        file.close()

        self.privateHex = privateHexUsable

    def simpleTransaction(self, password, reciever, txamount):
        return transaction(self.publicHex, reciever, txamount, round(time.time(), 2), self.retrievePrivate(password), self.retrieveNonce())

    def retrieveNonce(self):
        file = open("wallet.dat", 'r')
        wallet = json.loads(file.read())
        file.close()

        wallet["nonce"] = wallet["nonce"] + 1

        file = open("wallet.dat", 'w')
        file.write(json.dumps(wallet))
        file.close()

        return wallet["nonce"]

    def retrievePrivate(self, password):
        file = open("wallet.dat", 'r')
        wallet = json.loads(file.read())
        file.close()
        
        return cryptocode.decrypt(wallet["privateHex"], password)
        
    def retrievePublic(self):
        file = open("wallet.dat", 'r')
        wallet = json.loads(file.read())
        file.close()

        return wallet["publicHex"]

    def sign(self, message):
        privkey = ecdsa.SigningKey.from_string(bytes.fromhex(self.retrievePrivate()),curve=ecdsa.SECP256k1, hashfunc=sha256)
        
        return privkey.sign(message)

    def verify(self, message, intended):
        pubkey = ecdsa.VerifyingKey.from_string(bytes.fromhex(self.retrievePublic()),curve=ecdsa.SECP256k1, hashfunc=sha256)

        return pubkey.verify(message, intended)



##############################################################################
#non class functions
    
#cpu mining
def mine(block, miner, blockchain):
    global password
    startTime = time.time()

    diff = int(arbDifficulty(block.difficulty), 2)

    #add coinbase transaction
    block.transactions.append(transaction(''.join([("0") for x in range(64)]), miner.publicHex,math.floor((100 * 10 ** 9) / (2 ** (math.floor(block.height / 100000)))),round(time.time(), 2), miner.retrievePrivate(password),miner.retrieveNonce()).__dict__)
    for a in range(2 ** 32):
        header = int(stringHash(json.dumps(block.transactions) + str(block.previousBlock) + str(block.timeStamp)),16)
        for x in range(2**32):
            if (SHAKE6VAL(header, x) < diff):
                calculated = SHAKE6(header,x)
                print("Found nonce: " + str(x + (a*(2**32))) + "; Alterations: " + str(a))
                print("Hash: " + calculated)
                
                try:
                    if (x != 0):
                        print("Efficiency: " + str(round(round(x + (a*(2**32)))/(time.time() - startTime))) + " hashes per second")
                        print("Luck: " + str(round(int(block.difficulty,16)/x, 2)))
                    else:
                        print("nonce is 0")
                except:
                    print("infinite luck")

                block.proof = calculated
                block.addBlockToChain(blockchain, x, miner.publicHex)

                return
        
        block.complete(block.timeStamp + 0.01)
