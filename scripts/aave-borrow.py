from scripts.helpful_scripts import get_account
from brownie import network, config, interface
from scripts.get_weth import get_weth
from web3 import Web3

# 0.001
# amount = 1000000000000000
AMOUNT = Web3.toWei(0.001, "ether")


def main():
    account = get_account()
    print(f"account balance: {account.balance()/10**18}")
    erc20_address = config["networks"][network.show_active()]["weth_token"]
    # It will only get weth if on the mainnet-fork. On goerli I already have weth
    if network.show_active() in ["mainnet-fork"]:
        print("getting weth from mainnet-fork")
        get_weth()
    # Deposit into Aave lending pool
    # Get lending pool contract
    lending_pool = get_lending_pool()
    print(f"Lending pool contract: {lending_pool}")
    # Approve sending out ERC20 token
    approve_erc20(AMOUNT, lending_pool.address, erc20_address, account)
    # Deposit into Aave
    print("Depositing into Aave...")
    tx = lending_pool.deposit(
        erc20_address, AMOUNT, account.address, 0, {"from": account}
    )
    tx.wait(1)
    print("Deposited into Aave!!!")
    # how much?
    borrowable_eth, total_debt = get_borrowable_data(lending_pool, account)
    print("Let's borrow!")
    # DAI in terms of ETH
    dai_eth_price = get_asset_price(
        config["networks"][network.show_active()]["dai_eth_price_feed"]
    )
    # converting borrowable ETH into borrowable DAI x 95% (95% is just a liquidation safety)
    amount_of_dai_to_borrow = (1 / dai_eth_price) * (borrowable_eth * 0.95)
    print(f"We are going to borrow {amount_of_dai_to_borrow} DAI")
    dai_address = config["networks"][network.show_active()]["dai_token"]
    borrow_tx = lending_pool.borrow(
        dai_address,
        Web3.toWei(amount_of_dai_to_borrow, "ether"),
        1,
        0,
        account.address,
        {"from": account},
    )
    borrow_tx.wait(1)
    print("We borrowed some DAI!")
    get_borrowable_data(lending_pool, account)
    repay_all(Web3.toWei(amount_of_dai_to_borrow, "ether"), lending_pool, account)


def repay_all(amount, lending_pool, account):
    approve_erc20(
        Web3.toWei(amount, "ether"),
        lending_pool,
        config["networks"][network.show_active()]["dai_token"],
        account,
    )
    repay_tx = lending_pool.repay(
        config["networks"][network.show_active()]["dai_token"],
        amount,
        1,
        account.address,
        {"from": account},
    )
    repay_tx.wait(1)
    print("You just deposited, borrowed, and repayed with Aave, Brownie and Chainlink!")


def get_asset_price(price_feed_address):
    # ABI
    dai_eth_price_feed = interface.AggregatorV3Interface(price_feed_address)
    # Address
    latest_price = dai_eth_price_feed.latestRoundData()[1]
    converted_latest_price = Web3.fromWei(latest_price, "ether")
    print(f"The DAI/ETH price is {converted_latest_price}")
    return float(converted_latest_price)


def approve_erc20(amount, spender, erc20_address, account):
    print("Approving ERC20 token...")
    erc20 = interface.IERC20(erc20_address)
    tx = erc20.approve(spender, amount, {"from": account})
    tx.wait(1)
    print("ERC20 token Approved!!!")


def get_borrowable_data(lending_pool, account):
    (
        total_collateral_eth,
        total_debt_eth,
        available_borrow_eth,
        current_liquidation_threshold,
        ltv,
        health_factor,
    ) = lending_pool.getUserAccountData(account.address)
    # All of those variables are going to be returned in wei, let's convert them
    total_collateral_eth = Web3.fromWei(total_collateral_eth, "ether")
    total_debt_eth = Web3.fromWei(total_debt_eth, "ether")
    available_borrow_eth = Web3.fromWei(available_borrow_eth, "ether")
    print(f"You have {total_collateral_eth} worth of ETH deposited.")
    print(f"You have {total_debt_eth} worth of ETH borrowed.")
    print(f"You can borrow {available_borrow_eth} worth of ETH.")
    return (float(available_borrow_eth), float(total_debt_eth))


# gets the lending pool address and returns a lending pool contract
def get_lending_pool():
    # Contract Address
    lending_pool_addresses_provider = interface.ILendingPoolAddressesProvider(
        config["networks"][network.show_active()]["lending_pool_addresses_provider"]
    )
    lending_pool_address = lending_pool_addresses_provider.getLendingPool()
    # ABI
    lending_pool = interface.ILendingPool(lending_pool_address)
    return lending_pool
