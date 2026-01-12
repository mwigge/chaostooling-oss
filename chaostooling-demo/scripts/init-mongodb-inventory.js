// Initialize MongoDB with inventory items for production-scale demo
// This script runs automatically when MongoDB container starts (via /docker-entrypoint-initdb.d/)

// Create inventory collection with items (item_0 through item_99 with stock)
for (let i = 0; i < 100; i++) {
  db.inventory.updateOne(
    { item_id: 'item_' + i },
    { 
      $set: { 
        item_id: 'item_' + i,
        quantity: 1000,
        name: 'Item ' + i,
        price: 10.00 + (i * 0.50),
        created_at: new Date()
      }
    },
    { upsert: true }
  );
}

// Create index
db.inventory.createIndex({ item_id: 1 }, { unique: true });

print('Inventory initialized with 100 items (item_0 through item_99)');
print('Each item has 1000 units in stock');

