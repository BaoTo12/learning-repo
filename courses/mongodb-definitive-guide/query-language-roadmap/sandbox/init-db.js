const db = db.getSiblingDB('store_db');

print('================================================');
print('STARTING MQL PRACTICE SANDBOX DATA SEEDING');
print('================================================');

// 1. Drop existing collections to ensure a clean run
db.users.drop();
db.products.drop();
db.orders.drop();
db.pageviews.drop();
db.inventory.drop();
db.employees.drop();

// 2. Seed Products (100 items)
const categories = ['electronics', 'furniture', 'clothing', 'books', 'sports'];
const colors = ['red', 'blue', 'green', 'black', 'white'];
const products = [];

for (let i = 1; i <= 100; i++) {
  const category = categories[i % categories.length];
  const price = parseFloat((Math.random() * 490 + 10).toFixed(2)); // $10 to $500
  const stock = Math.floor(Math.random() * 150);
  const sku = 'SKU-' + (10000 + i);
  
  // Ratings array
  const ratings = [];
  const ratingCount = Math.floor(Math.random() * 6); // 0 to 5 ratings
  for (let r = 0; r < ratingCount; r++) {
    ratings.push(Math.floor(Math.random() * 3) + 3); // random ratings between 3 and 5
  }

  products.push({
    sku: sku,
    title: 'Product ' + i + ' - Brand New ' + category.toUpperCase(),
    category: category,
    price: price,
    stock: stock,
    ratings: ratings,
    specs: {
      weight: parseFloat((Math.random() * 15 + 0.1).toFixed(2)),
      color: colors[i % colors.length]
    },
    inStock: stock > 0
  });
}
db.products.insertMany(products);
print('✓ Seeded 100 products inside "products" collection.');

// 3. Seed Users (50 items)
const cities = ['Chicago', 'New York', 'Los Angeles', 'San Francisco', 'Houston', 'Miami'];
const roles = ['USER', 'ADMIN', 'GUEST'];
const statuses = ['ACTIVE', 'PENDING', 'INACTIVE', 'SUSPENDED'];
const users = [];

for (let i = 1; i <= 50; i++) {
  const username = 'user_' + i;
  const age = Math.floor(Math.random() * 50) + 18; // 18 to 67 years
  const status = statuses[i % statuses.length];
  const role = roles[i % roles.length];
  const joinedDate = new Date(Date.now() - Math.floor(Math.random() * 1000 * 60 * 60 * 24 * 365)); // past 1 year
  
  const user = {
    _id: i,
    username: username,
    email: username + '@example.com',
    age: age,
    status: status,
    role: role,
    joinedAt: joinedDate,
    address: {
      city: cities[i % cities.length],
      zip: String(10000 + i)
    }
  };

  // Mark 5% of users (1 in 20) as soft-deleted to support Module 12 patterns
  if (i % 20 === 0) {
    user.isDeleted = true;
    user.deletedAt = new Date(joinedDate.getTime() + 1000 * 60 * 60 * 24);
  }

  // Set legacyToken on some users to support $unset exercises
  if (i % 7 === 0) {
    user.legacyToken = 'TOK-LEG-' + Math.random().toString(36).substring(2, 10).toUpperCase();
  }

  users.push(user);
}
db.users.insertMany(users);
print('✓ Seeded 50 users inside "users" collection.');

// 4. Seed Orders (300 items)
const orders = [];
const orderStatuses = ['COMPLETED', 'PENDING', 'CANCELLED', 'SHIPPED'];

for (let i = 1; i <= 300; i++) {
  const customerId = Math.floor(Math.random() * 50) + 1; // map to existing user _id (1 to 50)
  const itemCount = Math.floor(Math.random() * 3) + 1; // 1 to 3 items
  const orderItems = [];
  let amount = 0;
  
  for (let j = 0; j < itemCount; j++) {
    const randomProduct = products[Math.floor(Math.random() * products.length)];
    const qty = Math.floor(Math.random() * 3) + 1;
    orderItems.push({
      sku: randomProduct.sku,
      qty: qty,
      price: randomProduct.price
    });
    amount += randomProduct.price * qty;
  }
  
  orders.push({
    orderId: 'ORD-' + (100000 + i),
    customerId: customerId,
    items: orderItems,
    amount: parseFloat(amount.toFixed(2)),
    status: orderStatuses[i % orderStatuses.length],
    createdAt: new Date(Date.now() - Math.floor(Math.random() * 1000 * 60 * 60 * 24 * 30)) // past 30 days
  });
}
db.orders.insertMany(orders);
print('✓ Seeded 300 orders inside "orders" collection.');

// 5. Seed Inventory (10 items - supporting Module 11 array updates scenario)
const inventoryDocs = [
  {
    _id: 999,
    warehouse: "MAIN_WAREHOUSE",
    bins: [
      { binId: "BIN-1", qty: 100, status: "OK" },
      { binId: "BIN-2", qty: 10, status: "LOW" },
      { binId: "BIN-3", qty: 5, status: "LOW" }
    ]
  }
];

for (let i = 1; i <= 9; i++) {
  inventoryDocs.push({
    _id: i,
    warehouse: "WAREHOUSE_" + i,
    bins: [
      { binId: "BIN-1", qty: Math.floor(Math.random() * 100) + 10, status: "OK" },
      { binId: "BIN-2", qty: Math.floor(Math.random() * 20), status: "LOW" }
    ]
  });
}
db.inventory.insertMany(inventoryDocs);
print('✓ Seeded 10 warehouse inventory objects.');

// 6. Seed Employees (10 items - for Module 15 recursive $graphLookup tests)
db.employees.insertMany([
  { _id: 1, name: "Alice", reportsTo: null, department: "Executive" },
  { _id: 2, name: "Bob", reportsTo: "Alice", department: "Engineering" },
  { _id: 3, name: "Charlie", reportsTo: "Alice", department: "Sales" },
  { _id: 4, name: "David", reportsTo: "Bob", department: "Engineering" },
  { _id: 5, name: "Emma", reportsTo: "Bob", department: "Engineering" },
  { _id: 6, name: "Frank", reportsTo: "Charlie", department: "Sales" },
  { _id: 7, name: "Grace", reportsTo: "Charlie", department: "Sales" },
  { _id: 8, name: "Henry", reportsTo: "David", department: "Engineering" },
  { _id: 9, name: "Ivy", reportsTo: "David", department: "Engineering" },
  { _id: 10, name: "Jack", reportsTo: "Emma", department: "Engineering" }
]);
print('✓ Seeded 10 organizational hierarchy structures inside "employees" collection.');

print('================================================');
print('SANDBOX SEEDING COMPLETED SUCCESSFULLY!');
print('================================================');
