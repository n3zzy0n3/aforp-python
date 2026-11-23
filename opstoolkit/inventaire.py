servers = [
  {"name": "web01", "ip": "10.0.0.11", "role": "web", "cpu": 72, "up": True},
  {"name": "web02", "ip": "10.0.0.12", "role": "web", "cpu": 95, "up": True},
  {"name": "db01", "ip": "10.0.0.21", "role": "db", "cpu": 40, "up": False},
  {"name": "cache01", "ip": "10.0.0.31", "role": "cache", "cpu": 15, "up": True}
]

def count_by_role(servers): 
    counts = {}
    for s in servers:
        counts[s["role"]] = counts.get(s["role"], 0) + 1
    return counts


def down_servers(servers):
	counts = []
	for s in servers:
		if not s["up"]:
			counts.append(s["name"]) 
	return counts


def overloaded(servers, threshold=90): 
	counts = []
	for s in servers:
		if s["cpu"] > threshold:
			counts.append(s["name"])
	return counts


def print_table(servers: list[dict], threshold:int):
        print(f"{'NOM':<10}{'IP':<12}{'ROLE':<8}{'CPU':>5} ETAT")


print(*sorted(servers, key=lambda s: s["cpu"], reverse=True), sep='\n', )




print_table(servers,90) 
