#!/bin/bash
# Initialize MongoDB with inventory items for production-scale demo

set -e

MONGODB_HOST=${MONGODB_HOST:-mongodb}
MONGODB_PORT=${MONGODB_PORT:-27017}
MONGODB_DB=${MONGODB_DB:-test}

echo "Waiting for MongoDB to be ready..."
until mongosh --host $MONGODB_HOST --port $MONGODB_PORT --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; do
  echo "MongoDB is unavailable - sleeping"
  sleep 2
done

echo "MongoDB is ready - initializing inventory..."

# Create inventory items (item_0 through item_99 with stock)
mongosh --host $MONGODB_HOST --port $MONGODB_PORT $MONGODB_DB --eval "
  // Create inventory collection with items
  for (let i = 0; i < 100; i++) {
    db.inventory.updateOne(
      { item_id: 'item_' + i },
      { 
        \$set: { 
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
"

echo "MongoDB inventory initialized successfully!"

